# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SubcontractorDeliveryRequestInherit(models.Model):
    _inherit = 'subcontractor.delivery.request'

    def _get_project_analytic_dist(self):
        """Get analytic distribution dict for project main cost center."""
        project = self.project_id or (
            self.contract_id and self.contract_id.project_id)
        if project and project.analytic_account_id:
            return {str(project.analytic_account_id.id): 100.0}
        return {}

    # -------------------------------------------------------------------------
    # Build prev_done and lines vals (same pattern as completion request)
    # -------------------------------------------------------------------------
    def _build_prev_done(self):
        """Return {item_id: total_qty_done} from confirmed/paid delivery requests."""
        confirmed = self.env['subcontractor.delivery.request'].search([
            ('contract_id', '=', self.contract_id.id),
            ('state', 'in', ('confirm', 'paid')),
            ('id', '!=', self.id),
        ])
        prev_done = {}
        for req in confirmed:
            for line in req.subcontractor_delivery_request_line_ids:
                if line.quantity > 0 and line.state in ('accept', 'partially'):
                    prev_done[line.item_id.id] = (
                        prev_done.get(line.item_id.id, 0) + line.quantity)
        return prev_done

    def _build_lines_vals(self):
        """Build line values from contract for auto-load."""
        if not self.contract_id:
            return []
        prev_done = self._build_prev_done()
        lines = []
        for cl in self.contract_id.owner_contract_line_ids:
            if not cl.item_id:
                continue
            prev_qty = prev_done.get(cl.item_id.id, 0)
            remaining = cl.quantity - prev_qty
            if remaining <= 0:
                continue
            lines.append({
                'item_id': cl.item_id.id,
                'description': cl.description,
                'uom_id': cl.uom_id.id if cl.uom_id else False,
                'price_unit': cl.price_unit,
                'contract_qty': cl.quantity,
                'prev_completed_qty': prev_qty,
                'analytic_distribution': cl.analytic_distribution or {},
                'quantity': 0,
                'amount': 0,
                'percentage': 0,
                'state': ' ',
            })
        return lines

    def _reload_lines_from_contract(self, force=False):
        """Clear and recreate lines from contract."""
        if not force and self.subcontractor_delivery_request_line_ids:
            return
        self.subcontractor_delivery_request_line_ids.unlink()
        for vals in self._build_lines_vals():
            vals['subcontractor_delivery_request_id'] = self.id
            self.env['subcontractor.delivery.request.line'].create(vals)

    @api.model
    def create(self, vals_list):
        """Override to auto-populate lines from contract."""
        records = super().create(vals_list)
        for rec in records:
            if rec.contract_id and not rec.subcontractor_delivery_request_line_ids:
                rec._reload_lines_from_contract()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'contract_id' in vals:
            for rec in self:
                if rec.contract_id and rec.state == 'draft':
                    rec._reload_lines_from_contract()
        return result

    def action_load_contract_lines(self):
        """Button: Reload lines from contract. Protected from overwriting entered qty."""
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_("Please select a contract first."))
        if self.state != 'draft':
            raise UserError(_("Lines can only be reloaded in Draft state."))
        has_entered = self.subcontractor_delivery_request_line_ids.filtered(
            lambda x: x.quantity > 0)
        if has_entered:
            raise UserError(_(
                "Some lines already have quantities entered. "
                "Delete them first if you want to reload from contract."))
        lines_vals = self._build_lines_vals()
        if not lines_vals:
            raise UserError(_("All contract items are fully completed."))
        self._reload_lines_from_contract(force=True)
        return True

    @api.onchange('contract_id')
    def _onchange_contract_id_load_lines(self):
        if self.contract_id and self.state == 'draft':
            self.subcontractor_delivery_request_line_ids = [(5,)]
            new_lines = []
            for vals in self._build_lines_vals():
                new_lines.append((0, 0, vals))
            self.subcontractor_delivery_request_line_ids = new_lines

    # -------------------------------------------------------------------------
    # Override action_confirm: auto-approve lines, apply contract deductions
    # -------------------------------------------------------------------------
    def action_confirm(self):
        """Override: allow 0-qty lines, auto-approve, apply contract deductions."""
        self.ensure_one()

        # Auto-approve lines with qty > 0
        has_any = False
        for line in self.subcontractor_delivery_request_line_ids:
            if line.quantity > 0:
                has_any = True
                if line.state == ' ':
                    line.write({
                        'amount': line.quantity * line.price_unit,
                        'percentage': 1.0,
                        'state': 'accept',
                    })
            else:
                line.write({'state': ' ', 'amount': 0, 'percentage': 0})

        if not has_any:
            raise UserError(_('Please enter quantity for at least one line.'))

        valid_lines = self.subcontractor_delivery_request_line_ids.filtered(
            lambda x: x.quantity > 0 and x.state in ('accept', 'partially'))
        invoice_subtotal = sum(valid_lines.mapped('amount'))

        # Create deductions for partially approved lines
        partially_approved = valid_lines.filtered(lambda x: x.state == 'partially')
        if partially_approved:
            self.action_create_deductions(partially_approved)
            self.action_create_contract_deductions(partially_approved)

        # Auto-create delivery deductions from contract deduction definitions
        self._create_delivery_deductions_from_contract(invoice_subtotal)

        # Auto-create delivery allowances from contract allowance definitions
        self._create_delivery_allowances_from_contract(invoice_subtotal)

        # Down payment recovery
        if self.contract_id.down_payment_percentage > 0:
            self._create_down_payment_recovery(invoice_subtotal)

        # Update contract finished quantities
        self.recompute_contract_qty()

        self.state = 'confirm'
        self.confirmation_date = fields.Date.today()

    def _create_delivery_deductions_from_contract(self, invoice_subtotal):
        """Mirror contract deduction lines into this delivery request."""
        if not self.contract_id.deduction_line_ids:
            return
        for ded in self.contract_id.deduction_line_ids:
            existing = self.deduction_line_ids.filtered(
                lambda x: x.name == ded.name)
            if existing:
                continue
            if not ded.amount and not ded.percentage:
                continue
            ded_amount = (
                invoice_subtotal * ded.percentage
                if ded.percentage else ded.amount)
            if ded_amount <= 0:
                continue
            vals = {
                'name': ded.name or _('Deduction'),
                'request_id': self.id,
                'main_type': 'deduction',
                'contract_type': 'subcontractor',
                'percentage': ded.percentage,
                'amount': ded_amount,
            }
            self.env['sub.contract.delivery.deduction.allowance'].create(vals)

    def _create_delivery_allowances_from_contract(self, invoice_subtotal):
        """Mirror contract allowance lines into this delivery request."""
        if not self.contract_id.allowance_line_ids:
            return
        for allow in self.contract_id.allowance_line_ids:
            existing = self.allowance_line_ids.filtered(
                lambda x: x.name == allow.name)
            if existing:
                continue
            if not allow.amount and not allow.percentage:
                continue
            allow_amount = (
                invoice_subtotal * allow.percentage
                if allow.percentage else allow.amount)
            if allow_amount <= 0:
                continue
            vals = {
                'name': allow.name or _('Allowance'),
                'request_id': self.id,
                'main_type': 'allowance',
                'contract_type': 'subcontractor',
                'percentage': allow.percentage,
                'amount': allow_amount,
            }
            self.env['sub.contract.delivery.deduction.allowance'].create(vals)

    def _create_down_payment_recovery(self, invoice_subtotal):
        """Create down payment recovery deduction."""
        existing = self.deduction_line_ids.filtered(
            lambda x: 'down payment' in (x.name or '').lower()
            or 'دفعة مقدمة' in (x.name or ''))
        if existing:
            return
        recovery_amount = invoice_subtotal * self.contract_id.down_payment_percentage
        if recovery_amount <= 0:
            return
        self.env['sub.contract.delivery.deduction.allowance'].create({
            'name': _('Down Payment Recovery - %s') % self.name,
            'request_id': self.id,
            'main_type': 'deduction',
            'contract_type': 'subcontractor',
            'percentage': self.contract_id.down_payment_percentage,
            'amount': recovery_amount,
        })

    # -------------------------------------------------------------------------
    # Override create_bill: actual qty + analytic on all lines
    # -------------------------------------------------------------------------
    def create_bill(self):
        """Override to add project analytic distribution to all invoice lines."""
        if not self.contract_id.partner_id:
            raise UserError(_('Please select a sub-contractor.'))

        delivery_journal_account_id = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'nthub_constructions.vendor_delivery_journal_account_id', '0') or '0')
        delivery_request_account_id = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'nthub_constructions.vendor_delivery_request_account_id', '0') or '0')

        project_analytic = self._get_project_analytic_dist()

        invoice_vals = {
            'ref': self.name,
            'invoice_date': self.date,
            'partner_id': self.contract_id.partner_id.id,
            'move_type': 'in_invoice',
            'invoice_line_ids': [],
        }
        if delivery_journal_account_id:
            invoice_vals['journal_id'] = delivery_journal_account_id

        # Approved delivery lines - actual qty and unit price
        approved_lines = self.subcontractor_delivery_request_line_ids.filtered(
            lambda x: x.quantity > 0 and x.state in ('accept', 'partially'))
        for line in approved_lines:
            line_vals = {
                'name': line.description or line.item_id.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'analytic_distribution': line.analytic_distribution or project_analytic,
            }
            if delivery_request_account_id:
                line_vals['account_id'] = delivery_request_account_id
            invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

        # Deductions (استقطاعات) - NEGATIVE
        for ded in self.deduction_line_ids:
            if not ded.amount:
                continue
            ded_vals = {
                'name': ded.name or _('Deduction'),
                'quantity': 1,
                'price_unit': -abs(ded.amount),
                'analytic_distribution': project_analytic,
            }
            if delivery_request_account_id:
                ded_vals['account_id'] = delivery_request_account_id
            invoice_vals['invoice_line_ids'].append((0, 0, ded_vals))

        # Allowances (إضافات) - POSITIVE
        for allow in self.allowance_line_ids:
            if not allow.amount:
                continue
            allow_vals = {
                'name': allow.name or _('Allowance'),
                'quantity': 1,
                'price_unit': abs(allow.amount),
                'analytic_distribution': project_analytic,
            }
            if delivery_request_account_id:
                allow_vals['account_id'] = delivery_request_account_id
            invoice_vals['invoice_line_ids'].append((0, 0, allow_vals))

        bill = self.env['account.move'].sudo().create(invoice_vals)
        self.bill_id = bill.id
        bill.action_post()
        self.state = 'paid'
