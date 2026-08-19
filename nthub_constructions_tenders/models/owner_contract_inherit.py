# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class OwnerContractInherit(models.Model):
    _inherit = 'owner.contract'

    down_payment_invoice_id = fields.Many2one('account.move', string=_('Down Payment Invoice'))
    down_payment_invoice_ids = fields.One2many(
        'account.move', 'contract_down_payment_id',
        string=_('Down Payment Invoices'))
    down_payment_invoice_count = fields.Integer(
        compute='_compute_down_payment_invoice_count')
    down_payment_invoiced = fields.Float(
        string=_('Down Payment Invoiced'),
        compute='_compute_down_payment_invoiced')
    down_payment_remaining = fields.Float(
        string=_('Down Payment Remaining'),
        compute='_compute_down_payment_invoiced')

    # -------------------------------------------------------------------------
    # Deduction Return Fields
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Variation Orders
    # -------------------------------------------------------------------------
    variation_order_ids = fields.One2many(
        'owner.variation.order', 'contract_id',
        string=_('Variation Orders / عقود تكميلية'))
    variation_order_count = fields.Integer(
        string=_('Variation Orders'),
        compute='_compute_variation_order_count')

    def _compute_variation_order_count(self):
        for rec in self:
            rec.variation_order_count = len(rec.variation_order_ids)

    def action_open_variation_orders(self):
        self.ensure_one()
        return {
            'name':    _('عقود تكميلية / Variation Orders'),
            'type':    'ir.actions.act_window',
            'res_model': 'owner.variation.order',
            'view_mode': 'list,form',
            'domain':  [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    # -------------------------------------------------------------------------
    # Deduction Return Fields
    # -------------------------------------------------------------------------
    deduction_return_invoice_ids = fields.One2many(
        'account.move', 'deduction_return_contract_id',
        string=_('Deduction Return Invoices'))
    deduction_return_invoice_count = fields.Integer(
        string=_('Deduction Return Invoices'),
        compute='_compute_deduction_return_totals')
    total_deductions_retained = fields.Float(
        string=_('Total Retained Deductions'),
        compute='_compute_deduction_return_totals')
    total_deduction_return_invoiced = fields.Float(
        string=_('Deduction Return Invoiced'),
        compute='_compute_deduction_return_totals')
    deduction_return_remaining = fields.Float(
        string=_('Deduction Return Remaining'),
        compute='_compute_deduction_return_totals')

    @api.depends('down_payment_invoice_ids', 'down_payment_invoice_ids.state',
                 'down_payment_invoice_ids.amount_untaxed_signed', 'down_payment')
    def _compute_down_payment_invoiced(self):
        for rec in self:
            total = sum(
                inv.amount_untaxed_signed
                for inv in rec.down_payment_invoice_ids
                if inv.state != 'cancel'
            )
            rec.down_payment_invoiced = abs(total)
            rec.down_payment_remaining = rec.down_payment - abs(total)

    def _compute_down_payment_invoice_count(self):
        for rec in self:
            rec.down_payment_invoice_count = len(rec.down_payment_invoice_ids)

    # -------------------------------------------------------------------------
    # Deduction Return Computations (non-stored - recompute on form load)
    # -------------------------------------------------------------------------
    def _compute_deduction_return_totals(self):
        for rec in self:
            active = rec.deduction_return_invoice_ids.filtered(
                lambda x: x.state != 'cancel')
            rec.deduction_return_invoice_count = len(active)
            returned = sum(abs(inv.amount_untaxed_signed) for inv in active)
            rec.total_deduction_return_invoiced = returned
            retained = rec._get_total_deductions_retained()
            rec.total_deductions_retained = retained
            rec.deduction_return_remaining = retained - returned

    def _get_total_deductions_retained(self):
        if self.is_owner:
            deductions = self.env['contract.completion.deduction.allowance'].search([
                ('request_id.contract_id', '=', self.id),
                ('request_id.state', 'in', ('confirm', 'invoiced')),
                ('main_type', '=', 'deduction'),
            ])
        else:
            deductions = self.env['sub.contract.delivery.deduction.allowance'].search([
                ('request_id.contract_id', '=', self.id),
                ('request_id.state', 'in', ('confirm', 'paid')),
                ('main_type', '=', 'deduction'),
            ])
        return sum(d.amount for d in deductions)

    def _get_deduction_lines_for_return(self):
        if self.is_owner:
            deductions = self.env['contract.completion.deduction.allowance'].search([
                ('request_id.contract_id', '=', self.id),
                ('request_id.state', 'in', ('confirm', 'invoiced')),
                ('main_type', '=', 'deduction'),
            ])
        else:
            deductions = self.env['sub.contract.delivery.deduction.allowance'].search([
                ('request_id.contract_id', '=', self.id),
                ('request_id.state', 'in', ('confirm', 'paid')),
                ('main_type', '=', 'deduction'),
            ])
        grouped = {}
        for ded in deductions:
            key = ded.name or 'Deduction'
            if key not in grouped:
                grouped[key] = {'amount': 0.0, 'account_id': False}
            grouped[key]['amount'] += ded.amount
            if not grouped[key]['account_id'] and hasattr(ded, 'account_id') and ded.account_id:
                grouped[key]['account_id'] = ded.account_id.id
        return grouped

    def action_create_deduction_return_invoice(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please select a customer/vendor on the contract.'))
        retained = self._get_total_deductions_retained()
        if retained <= 0:
            raise UserError(_('No deductions have been retained for this contract.'))
        already_returned = sum(
            abs(inv.amount_untaxed_signed)
            for inv in self.deduction_return_invoice_ids
            if inv.state != 'cancel'
        )
        remaining = retained - already_returned
        if remaining <= 0.01:
            raise UserError(_('All retained deductions have already been returned.'))
        project_analytic = self._get_project_analytic_dist()
        move_type = 'out_invoice' if self.is_owner else 'in_invoice'
        grouped = self._get_deduction_lines_for_return()
        invoice_lines = []
        for name, info in grouped.items():
            line_vals = {
                'name': 'Return: %s' % name,
                'quantity': 1,
                'price_unit': info['amount'],
            }
            if info['account_id']:
                line_vals['account_id'] = info['account_id']
            if project_analytic:
                line_vals['analytic_distribution'] = project_analytic
            invoice_lines.append((0, 0, line_vals))
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_id.id,
            'move_type': move_type,
            'invoice_date': fields.Date.today(),
            'ref': 'Deduction Return - %s' % self.name,
            'deduction_return_contract_id': self.id,
            'invoice_line_ids': invoice_lines,
        })
        return {
            'name': _('Deduction Return Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

    def action_open_deduction_return_invoices(self):
        return {
            'name': _('Deduction Return Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('deduction_return_contract_id', '=', self.id)],
            'target': 'current',
        }

    def _get_project_analytic_dist(self):
        if self.project_id and self.project_id.analytic_account_id:
            return {str(self.project_id.analytic_account_id.id): 100.0}
        return {}

    def action_create_expenses_invoice(self):
        if not self.partner_id:
            raise UserError(_('Please select a customer.'))
        project_analytic = self._get_project_analytic_dist()
        self.extra_expense_invoice_id = self.env['account.move'].create({
            'ref': 'Extra Expenses invoice for Contract %s' % self.name,
            'partner_id': self.partner_id.id,
            'move_type': 'out_invoice',
            'invoice_date': datetime.now().date(),
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': rec.product_id.id,
                    'price_unit': rec.cost,
                    'quantity': 1,
                    'analytic_distribution': project_analytic,
                }) for rec in self.project_extra_expenses_ids],
        })
        return {
            'name': _('Extra expenses invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.extra_expense_invoice_id.id,
            'target': 'current',
        }

    budget_created = fields.Boolean(default=False, copy=False)
    budget_analytic_id = fields.Many2one('budget.analytic', string=_('Budget'), readonly=True, copy=False)

    def action_open_budget(self):
        self.ensure_one()
        if not self.budget_analytic_id:
            raise UserError(_('No budget created for this contract.'))
        return {
            'name': _('Budget'),
            'type': 'ir.actions.act_window',
            'res_model': 'budget.analytic',
            'view_mode': 'form',
            'res_id': self.budget_analytic_id.id,
            'target': 'current',
        }

    def action_confirm(self):
        res = super().action_confirm()
        for contract in self:
            if not contract.is_owner or not contract.project_id:
                continue
            tender_lines = contract.project_id.tender_ids
            if tender_lines:
                for contract_line in contract.owner_contract_line_ids:
                    if not contract_line.item_id:
                        continue
                    matching = tender_lines.filtered(
                        lambda t, cl=contract_line: t.item_id.id == cl.item_id.id
                    )
                    if matching:
                        matching[0].write({
                            'qty': contract_line.quantity,
                            'unit_price': contract_line.cost_price,
                        })
            contract._create_contract_budget_lines()
        return res

    def _create_contract_budget_lines(self):
        if self.budget_created:
            return
        if not self.owner_contract_line_ids:
            return
        budget_analytic = self.env['budget.analytic'].search([
            ('name', 'ilike', self.name),
        ], limit=1)
        if not budget_analytic:
            ba_vals = {'name': 'Budget - %s' % self.name}
            if hasattr(self.env['budget.analytic'], 'date_from'):
                ba_vals['date_from'] = self.date or fields.Date.today()
            if hasattr(self.env['budget.analytic'], 'date_to'):
                ba_vals['date_to'] = self.end_date or fields.Date.today()
            budget_analytic = self.env['budget.analytic'].create(ba_vals)
        for cl in self.owner_contract_line_ids:
            if not cl.item_id:
                continue
            analytic_account_id = False
            if cl.analytic_distribution:
                for acc_id in cl.analytic_distribution:
                    analytic_account_id = int(acc_id)
                    break
            if not analytic_account_id:
                if self.project_id and self.project_id.analytic_account_id:
                    analytic_account_id = self.project_id.analytic_account_id.id
            if not analytic_account_id:
                continue
            cost_total = cl.cost_price * cl.quantity
            existing = self.env['budget.line'].search([
                ('budget_analytic_id', '=', budget_analytic.id),
                ('account_id', '=', analytic_account_id),
            ], limit=1)
            if existing:
                existing.budget_amount += cost_total
            else:
                self.env['budget.line'].create({
                    'budget_analytic_id': budget_analytic.id,
                    'account_id': analytic_account_id,
                    'budget_amount': cost_total,
                })
        self.budget_analytic_id = budget_analytic.id
        self.budget_created = True
        self._recompute_budget_amounts()

    def _recompute_budget_amounts(self):
        for cl in self.owner_contract_line_ids:
            budget_amount = 0
            if cl.analytic_distribution:
                for key, value in cl.analytic_distribution.items():
                    analytic_account = self.env['account.analytic.account'].browse(
                        int(key.split(",")[0]))
                    budget_lines = self.env['budget.line'].search([
                        ('account_id', '=', analytic_account.id)])
                    for bl in budget_lines:
                        budget_amount += bl.budget_amount * value / 100
            cl.write({'budget_amount': budget_amount})
        if self.project_id:
            breakdown_model = self.env['tender.job.cost.line']
            if 'tender.job.cost.line' not in self.env:
                return
            breakdown_lines = breakdown_model.search([
                ('job_cost_id.project_id', '=', self.project_id.id),
            ])
            for jc_line in breakdown_lines:
                budget_amount = 0
                if jc_line.analytic_distribution:
                    for key, value in jc_line.analytic_distribution.items():
                        analytic_account = self.env['account.analytic.account'].browse(
                            int(key.split(",")[0]))
                        budget_lines = self.env['budget.line'].search([
                            ('account_id', '=', analytic_account.id)])
                        for bl in budget_lines:
                            budget_amount += bl.budget_amount * value / 100
                jc_line.write({'budget_amount': budget_amount})

    def create_subcontractor_delivery_request(self):
        prev_done = {}
        confirmed = self.env['subcontractor.delivery.request'].search([
            ('contract_id', '=', self.id),
            ('state', 'in', ('confirm', 'paid')),
        ])
        for req in confirmed:
            for line in req.subcontractor_delivery_request_line_ids:
                if line.quantity > 0 and line.state in ('accept', 'partially'):
                    prev_done[line.item_id.id] = (
                        prev_done.get(line.item_id.id, 0) + line.quantity)
        delivery_lines = []
        for cl in self.owner_contract_line_ids:
            if not cl.item_id:
                continue
            prev_qty = prev_done.get(cl.item_id.id, 0)
            remaining = cl.quantity - prev_qty
            if remaining <= 0:
                continue
            delivery_lines.append((0, 0, {
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
            }))
        vals = {
            'project_id': self.project_id.id,
            'contract_id': self.id,
            'date': fields.Date.today(),
            'reference': self.reference.id if self.reference else False,
            'type': 'initial',
            'state': 'draft',
            'subcontractor_delivery_request_line_ids': delivery_lines,
        }
        delivery_req = self.env['subcontractor.delivery.request'].create(vals)
        return {
            'name': _('Subcontractor Delivery Request'),
            'view_mode': 'form',
            'res_model': 'subcontractor.delivery.request',
            'res_id': delivery_req.id,
            'type': 'ir.actions.act_window',
            'context': {'form_view_initial_mode': 'edit'},
            'target': 'current',
        }

    def _get_down_payment_account(self):
        account_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'nthub_tenders.down_payment_account_id', '0') or '0')
        if account_id:
            account = self.env['account.account'].browse(account_id).exists()
            if account:
                return account
        deduction_type = self.env['tender.deduction.type'].search(
            [('name', 'ilike', 'down payment')], limit=1)
        if not deduction_type:
            deduction_type = self.env['tender.deduction.type'].search(
                [('name', 'ilike', 'down payment')], limit=1)
        if deduction_type and deduction_type.account_id:
            return deduction_type.account_id
        return False

    def _get_or_create_down_payment_product(self):
        """Get the Down Payment product. Robust against the product being
        archived (e.g. via tender item deletion) or renamed/translated:
        1. search by internal reference (default_code) including archived,
        2. search by name (en/ar) including archived,
        3. unarchive if found archived,
        4. create it if it really doesn't exist.
        """
        Product = self.env['product.product'].with_context(active_test=False)
        product = Product.search(
            [('default_code', '=', 'DOWN_PAYMENT')], limit=1)
        if not product:
            product = Product.search(
                ['|', ('name', '=', 'Down Payment'),
                      ('name', '=', 'دفعة مقدمة')], limit=1)
        if product:
            if not product.active:
                product.active = True
            if not product.default_code:
                product.default_code = 'DOWN_PAYMENT'
            return product
        return self.env['product.product'].create({
            'name': 'Down Payment',
            'default_code': 'DOWN_PAYMENT',
            'type': 'service',
            'sale_ok': True,
            'purchase_ok': True,
        })

    def _create_down_payment_invoice(self, amount, move_type='out_invoice'):
        if not self.partner_id:
            raise UserError(_('Please select a customer/sub-contractor.'))
        if amount <= 0:
            raise UserError(_('Invoice amount must be greater than zero.'))
        remaining = self.down_payment - self.down_payment_invoiced
        if amount > remaining + 0.01:
            raise UserError(
                _('Invoice amount (%.2f) exceeds remaining down payment (%.2f).')
                % (amount, remaining))
        product = self._get_or_create_down_payment_product()
        account = self._get_down_payment_account()
        project_analytic = {}
        if self.project_id and self.project_id.analytic_account_id:
            project_analytic = {str(self.project_id.analytic_account_id.id): 100.0}
        line_vals = {
            'product_id': product.id,
            'name': 'Down Payment - %s' % self.name,
            'quantity': 1,
            'price_unit': amount,
        }
        if account:
            line_vals['account_id'] = account.id
        if project_analytic:
            line_vals['analytic_distribution'] = project_analytic
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_id.id,
            'move_type': move_type,
            'invoice_date': datetime.now().date(),
            'ref': 'Down Payment - %s' % self.name,
            'contract_down_payment_id': self.id,
            'invoice_line_ids': [(0, 0, line_vals)],
        })
        # Safety guard: never return a silently-empty invoice.
        if not invoice.invoice_line_ids:
            invoice.write({'invoice_line_ids': [(0, 0, dict(line_vals))]})
        if not invoice.invoice_line_ids:
            raise UserError(_(
                'The down payment invoice was created without lines. '
                'Please check the Down Payment product and account settings.'))
        if not self.down_payment_invoice_id:
            self.down_payment_invoice_id = invoice.id
        return invoice

    def _get_down_payment_remaining(self):
        total = sum(
            abs(inv.amount_untaxed_signed)
            for inv in self.down_payment_invoice_ids
            if inv.state != 'cancel'
        )
        return self.down_payment - total

    def create_payment(self):
        if not self.down_payment:
            raise UserError(_('Please enter a down payment amount.'))
        if self.down_payment > self.total_amount:
            raise UserError(
                _('The down payment amount cannot be greater than the total amount.'))
        remaining = self._get_down_payment_remaining()
        if remaining <= 0:
            raise UserError(_('Down payment has been fully invoiced.'))
        return {
            'name': _('Down Payment Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'down.payment.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
                'default_amount': remaining,
                'default_max_amount': remaining,
            },
        }

    def create_payment_from_down_payment(self):
        if not self.down_payment:
            raise UserError(_('Please enter a down payment amount.'))
        if self.down_payment > self.total_amount:
            raise UserError(
                _('The down payment amount cannot be greater than the total amount.'))
        remaining = self._get_down_payment_remaining()
        if remaining <= 0:
            raise UserError(_('Down payment has been fully invoiced.'))
        return {
            'name': _('Down Payment Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'down.payment.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
                'default_amount': remaining,
                'default_max_amount': remaining,
                'default_is_vendor': True,
            },
        }

    def action_open_down_payment_invoices(self):
        return {
            'name': _('Down Payment Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('contract_down_payment_id', '=', self.id)],
            'target': 'current',
        }
