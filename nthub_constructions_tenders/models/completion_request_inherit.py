# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

# XML IDs لمجموعات المستخلص — تُستخدم لتحديد المستلمين في الإشعارات
_GROUP_SITE_ENGINEER      = 'nthub_constructions_tenders.completion_group_site_engineer'
_GROUP_REVIEW_ENGINEER    = 'nthub_constructions_tenders.completion_group_review_engineer'
_GROUP_PROJECT_MANAGER    = 'nthub_constructions_tenders.completion_group_project_manager'
_GROUP_ACCOUNTANT         = 'nthub_constructions_tenders.completion_group_accountant'


class ProjectCompletionRequestInherit(models.Model):
    # الموديل الأساسي project.completion.request قد يكون لديه mail.thread بالفعل —
    # نستخدم _inherit = string عادي لضمان تسجيل الميثودز بشكل صحيح في Registry.
    _inherit = 'project.completion.request'

    # -------------------------------------------------------------------------
    # إشعارات المستخلص — helpers
    # -------------------------------------------------------------------------

    def _completion_group_users(self, group_xmlid):
        """إرجاع recordset لكل مستخدمي المجموعة المحددة."""
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        return group.user_ids if group else self.env['res.users']

    def _completion_notify(self, body, target_group_xmlid, activity_summary=None):
        """نشر رسالة في Chatter + إشعار بريد + نشاط للمجموعة المستهدفة.

        نستخدم hasattr لضمان التوافق مع أي نسخة من الموديل الأساسي سواء
        كان لديه mail.thread/mail.activity.mixin أم لا.

        Args:
            body: نص الرسالة (HTML)
            target_group_xmlid: XML ID مجموعة المستقبِلين
            activity_summary: ملخص النشاط (إن لم يُحدد لا يُنشأ نشاط)
        """
        target_users = self._completion_group_users(target_group_xmlid)
        partner_ids  = target_users.mapped('partner_id').ids

        # 1) رسالة في Chatter + إيميل للمستلمين (إذا كان الموديل يدعم mail.thread)
        if hasattr(self, 'message_post'):
            self.message_post(
                body=body,
                subtype_xmlid='mail.mt_comment',
                partner_ids=partner_ids,
            )

        # 2) نشاط (Activity) لكل مستخدم في المجموعة المستهدفة
        if activity_summary and target_users and hasattr(self, 'activity_schedule'):
            for user in target_users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=activity_summary,
                    note=body,
                    user_id=user.id,
                )

    # -------------------------------------------------------------------------
    # Helper: build prev_done dict for a contract
    # -------------------------------------------------------------------------
    def _build_prev_done(self):
        """Return dict {item_id: total_qty_done} from confirmed/invoiced requests."""
        confirmed = self.env['project.completion.request'].search([
            ('contract_id', '=', self.contract_id.id),
            ('state', 'in', ('confirm', 'invoiced')),
            ('id', '!=', self.id),
        ])
        prev_done = {}
        for req in confirmed:
            for line in req.line_ids:
                if line.quantity > 0 and line.state in ('accept', 'partially'):
                    prev_done[line.item_id.id] = (
                        prev_done.get(line.item_id.id, 0) + line.quantity)
        return prev_done

    def _get_project_analytic_dist(self):
        """Get analytic distribution dict for project main cost center."""
        project = self.project_id or (
            self.contract_id and self.contract_id.project_id)
        if project and project.analytic_account_id:
            return {str(project.analytic_account_id.id): 100.0}
        return {}

    def _build_lines_vals(self):
        """Build line values list from contract (used by onchange and create)."""
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
        """Internal: clear and recreate lines from contract (writes to DB).

        Only reloads if no lines exist, unless force=True.
        """
        if not force and self.line_ids:
            return  # Already has lines - don't overwrite existing work
        self.line_ids.unlink()
        lines_vals = self._build_lines_vals()
        for vals in lines_vals:
            vals['completion_request_id'] = self.id
            self.env['project.completion.request.line'].create(vals)

    # -------------------------------------------------------------------------
    # Override create: auto-populate lines when contract_id is set
    # -------------------------------------------------------------------------
    @api.model
    def create(self, vals_list):
        """Override to auto-populate lines from contract after creation."""
        records = super().create(vals_list)
        for rec in records:
            if rec.contract_id and not rec.line_ids:
                rec._reload_lines_from_contract()
        return records

    # -------------------------------------------------------------------------
    # Override write: auto-reload lines when contract_id changes
    # -------------------------------------------------------------------------
    def write(self, vals):
        result = super().write(vals)
        if 'contract_id' in vals:
            for rec in self:
                if rec.contract_id and rec.state == 'draft':
                    rec._reload_lines_from_contract()
        return result

    # -------------------------------------------------------------------------
    # Auto-load lines when contract is selected (UI onchange - shows in form)
    # -------------------------------------------------------------------------
    @api.onchange('contract_id')
    def _onchange_contract_id_load_lines(self):
        if self.contract_id and self.state == 'draft':
            self.line_ids = [(5,)]
            new_lines = []
            for vals in self._build_lines_vals():
                new_lines.append((0, 0, vals))
            self.line_ids = new_lines

    def action_load_contract_lines(self):
        """Button: Reload lines from contract.
        Protected: won't overwrite lines that have quantities entered.
        """
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_("Please select a contract first."))
        if self.state != 'draft':
            raise UserError(_("Lines can only be reloaded in Draft state."))
        # Protect entered work
        has_entered = self.line_ids.filtered(lambda x: x.quantity > 0)
        if has_entered:
            raise UserError(_(
                "Some lines already have quantities entered. "
                "Delete them first if you want to reload from contract."))
        lines_vals = self._build_lines_vals()
        if not lines_vals:
            raise UserError(_("All contract items are fully completed."))
        self._reload_lines_from_contract(force=True)
        return True

    # -------------------------------------------------------------------------
    # Return to Draft — للمهندس المراجع لإرجاع المستخلص للتعديل
    # -------------------------------------------------------------------------
    def action_return_to_draft(self):
        """إرجاع المستخلص لحالة المسودة — متاح لمهندس المراجعة فقط
        عندما يكون المستخلص قيد المراجعة (processing)."""
        for rec in self:
            if rec.state != 'processing':
                raise UserError(
                    _('لا يمكن الإرجاع للمسودة إلا من حالة "قيد المراجعة".'))
            rec.state = 'draft'
            # إشعار مهندس الموقع بالإرجاع
            submitter = rec.create_uid
            rec._completion_notify(
                body=_(
                    '<p>تم إرجاع المستخلص <b>%s</b> للمسودة بواسطة %s للمراجعة والتعديل.</p>'
                ) % (rec.name or '', self.env.user.name),
                target_group_xmlid=_GROUP_SITE_ENGINEER,
                activity_summary=_('مستخلص مُرجَع للتعديل — %s') % (rec.name or ''),
            )
        return True

    # -------------------------------------------------------------------------
    # Override start_processing - allow 0-qty lines (not billing this period)
    # -------------------------------------------------------------------------
    def start_processing(self):
        """Override: skip base validation that requires ALL lines to have qty>0.
        We allow lines with qty=0 (meaning: not billing this item this period).
        """
        has_any = False
        for line in self.line_ids:
            if line.quantity > 0:
                has_any = True
                if line.state == ' ':
                    line.write({
                        'amount': line.quantity * line.price_unit,
                        'percentage': 1.0,
                        'state': 'accept',
                    })
            else:
                # qty=0 → reset state to blank (not billing this period)
                line.write({'state': ' ', 'amount': 0, 'percentage': 0})
        if not has_any:
            raise UserError(_('Please enter quantity for at least one line.'))
        # Do NOT call super() - base raises error for any 0-qty line
        self.state = 'processing'
        # إشعار مهندس المراجعة بوجود مستخلص ينتظر مراجعته
        for rec in self:
            rec._completion_notify(
                body=_(
                    '<p>تم رفع المستخلص <b>%s</b> للمراجعة بواسطة %s — يرجى المراجعة والبت.</p>'
                ) % (rec.name or '', self.env.user.name),
                target_group_xmlid=_GROUP_REVIEW_ENGINEER,
                activity_summary=_('مستخلص ينتظر مراجعتك — %s') % (rec.name or ''),
            )
        return True

    # -------------------------------------------------------------------------
    # Override action_confirm
    # -------------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_("Please select a contract."))

        # Safety net: auto-approve lines with qty > 0
        for line in self.line_ids:
            if line.quantity > 0 and line.state == ' ':
                line.write({
                    'amount': line.quantity * line.price_unit,
                    'percentage': 1.0,
                    'state': 'accept',
                })

        valid_lines = self.line_ids.filtered(
            lambda x: x.quantity > 0 and x.state in ('accept', 'partially'))
        if not valid_lines:
            raise UserError(_(
                "No lines have a quantity greater than zero. "
                "Please enter quantities for at least one line."))

        invoice_subtotal = sum(valid_lines.mapped('amount'))

        # Create deductions for partially approved lines (underapproved qty)
        partially_approved = valid_lines.filtered(lambda x: x.state == 'partially')
        if partially_approved:
            self.action_create_deductions(partially_approved)

        # Auto-create completion deductions from contract deduction definitions
        self._create_completion_deductions_from_contract(invoice_subtotal)

        # Auto-create completion allowances from contract allowance definitions
        self._create_completion_allowances_from_contract(invoice_subtotal)

        # Down payment recovery (deduction) if contract has down payment %
        if self.contract_id.down_payment_percentage > 0:
            self._create_down_payment_recovery_deduction(invoice_subtotal)

        # Update contract line finished quantities
        for contract_line in self.contract_id.owner_contract_line_ids:
            cr_line = valid_lines.filtered(
                lambda x, cl=contract_line: x.item_id.id == cl.item_id.id)
            if cr_line:
                contract_line.finished_quantity += sum(
                    cr_line.mapped('quantity'))

        self.state = 'confirm'
        self.confirmation_date = fields.Date.today()
        # إشعار مدير المشروع بأن المستخلص بانتظار اعتماده
        self._completion_notify(
            body=_(
                '<p>تم قبول المستخلص <b>%s</b> من مهندس المراجعة وهو الآن بانتظار اعتمادك النهائي.</p>'
            ) % (self.name or ''),
            target_group_xmlid=_GROUP_PROJECT_MANAGER,
            activity_summary=_('مستخلص ينتظر اعتمادك — %s') % (self.name or ''),
        )

    # -------------------------------------------------------------------------
    # Create completion-level deductions from contract deduction definitions
    # -------------------------------------------------------------------------
    def _create_completion_deductions_from_contract(self, invoice_subtotal):
        """Mirror each contract deduction line into this completion request."""
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
                'contract_type': 'owner',
                'percentage': ded.percentage,
                'amount': ded_amount,
            }
            if hasattr(ded, 'deduction_type_id') and ded.deduction_type_id:
                vals['deduction_type_id'] = ded.deduction_type_id.id
            if hasattr(ded, 'account_id') and ded.account_id:
                vals['account_id'] = ded.account_id.id
            self.env['contract.completion.deduction.allowance'].create(vals)

    def _create_completion_allowances_from_contract(self, invoice_subtotal):
        """Mirror each contract allowance line into this completion request."""
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
                'contract_type': 'owner',
                'percentage': allow.percentage,
                'amount': allow_amount,
            }
            if hasattr(allow, 'deduction_type_id') and allow.deduction_type_id:
                vals['deduction_type_id'] = allow.deduction_type_id.id
            if hasattr(allow, 'account_id') and allow.account_id:
                vals['account_id'] = allow.account_id.id
            self.env['contract.completion.deduction.allowance'].create(vals)

    def _create_down_payment_recovery_deduction(self, invoice_subtotal):
        """Create down payment RECOVERY as a DEDUCTION (استرداد دفعة مقدمة)."""
        existing = self.deduction_line_ids.filtered(
            lambda x: 'down payment' in (x.name or '').lower()
            or 'دفعة مقدمة' in (x.name or ''))
        if existing:
            return
        allowance_type = self._get_allowance_type()
        recovery_amount = invoice_subtotal * self.contract_id.down_payment_percentage
        if recovery_amount <= 0:
            return
        vals = {
            'name': _('Down Payment Recovery - %s') % self.name,
            'request_id': self.id,
            'main_type': 'deduction',       # ← deduction: يُخصم من الفاتورة
            'contract_type': 'owner',
            'percentage': self.contract_id.down_payment_percentage,
            'amount': recovery_amount,
        }
        if allowance_type:
            vals['deduction_type_id'] = allowance_type.id
            if allowance_type.account_id:
                vals['account_id'] = allowance_type.account_id.id
        self.env['contract.completion.deduction.allowance'].create(vals)

    # -------------------------------------------------------------------------
    # Deduction helpers for partially approved lines
    # -------------------------------------------------------------------------
    def _get_deduction_type(self, name_hint='deduction'):
        return self.env['tender.deduction.type'].search(
            [('name', 'ilike', name_hint), ('type', '=', 'deduction')], limit=1)

    def _get_allowance_type(self, name_hint='down payment'):
        atype = self.env['tender.deduction.type'].search(
            [('name', 'ilike', name_hint), ('type', '=', 'allowance')], limit=1)
        if not atype:
            atype = self.env['tender.deduction.type'].search(
                [('name', 'ilike', 'دفعة مقدمة'), ('type', '=', 'allowance')], limit=1)
        if not atype:
            atype = self.env['tender.deduction.type'].search(
                [('type', '=', 'allowance')], limit=1)
        return atype

    def action_create_deductions(self, lines):
        """Create completion deductions for partially-approved lines."""
        deduction_type = (self._get_deduction_type('partial')
                          or self._get_deduction_type())
        for line in lines:
            vals = {
                'name': _('Deduction for Item: %s') % line.item_id.name,
                'item_id': line.item_id.id,
                'request_id': self.id,
                'main_type': 'deduction',
                'contract_type': 'owner',
                'percentage': 1 - line.percentage,
                'amount': line.total_amount - line.amount,
            }
            if deduction_type:
                vals['deduction_type_id'] = deduction_type.id
                if deduction_type.account_id:
                    vals['account_id'] = deduction_type.account_id.id
            self.env['contract.completion.deduction.allowance'].create(vals)

    # -------------------------------------------------------------------------
    # Invoice creation
    # -------------------------------------------------------------------------
    def create_completion_invoice(self):
        for rec in self:
            if rec.state != 'confirm':
                raise UserError(
                    _("You can only create an invoice for confirmed requests."))
            if not rec.contract_id.partner_id:
                raise UserError(_("Please select a customer on contract."))

            journal_id = int(
                self.env['ir.config_parameter'].sudo().get_param(
                    'nthub_constructions.customer_compilation_journal_account_id',
                    '0') or '0')
            default_account_id = int(
                self.env['ir.config_parameter'].sudo().get_param(
                    'nthub_constructions.customer_compilation_request_account_id',
                    '0') or '0')

            project_analytic = rec._get_project_analytic_dist()

            invoice_vals = {
                'partner_id': rec.contract_id.partner_id.id,
                'invoice_date': rec.date,
                'currency_id': rec.contract_id.currency_id.id,
                'move_type': 'out_invoice',
                'invoice_line_ids': [],
            }
            if journal_id:
                invoice_vals['journal_id'] = journal_id

            # 1. Approved lines (each with its own analytic)
            approved_lines = rec.line_ids.filtered(
                lambda x: x.quantity > 0 and x.state in ('accept', 'partially'))

            for line in approved_lines:
                line_vals = {
                    'product_id': (line.item_id.related_product_id.id
                                   if line.item_id.related_product_id else False),
                    'name': line.item_id.name,
                    'analytic_distribution': (
                        line.analytic_distribution or project_analytic),
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                }
                if default_account_id:
                    line_vals['account_id'] = default_account_id
                invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

            # 2. Deductions linked to this completion request (NEGATIVE - يُخصم)
            for ded in rec.deduction_line_ids:
                ded_amount = ded.amount
                if ded_amount <= 0:
                    continue
                ded_vals = {
                    'name': ded.name or _('Deduction'),
                    'quantity': 1,
                    'price_unit': -abs(ded_amount),   # always negative
                    'analytic_distribution': project_analytic,
                }
                if hasattr(ded, 'account_id') and ded.account_id:
                    ded_vals['account_id'] = ded.account_id.id
                elif default_account_id:
                    ded_vals['account_id'] = default_account_id
                invoice_vals['invoice_line_ids'].append((0, 0, ded_vals))

            # 3. Allowances linked to this completion request (POSITIVE - يُضاف)
            for allow in rec.allowance_line_ids:
                allow_amount = allow.amount
                if allow_amount <= 0:
                    continue
                allow_vals = {
                    'name': allow.name or _('Allowance'),
                    'quantity': 1,
                    'price_unit': abs(allow_amount),  # always positive (إضافة)
                    'analytic_distribution': project_analytic,
                }
                if hasattr(allow, 'account_id') and allow.account_id:
                    allow_vals['account_id'] = allow.account_id.id
                elif default_account_id:
                    allow_vals['account_id'] = default_account_id
                invoice_vals['invoice_line_ids'].append((0, 0, allow_vals))

            invoice = self.env['account.move'].create(invoice_vals)
            rec.invoice_id = invoice.id
            invoice.action_post()
            rec.write({'state': 'invoiced'})
            # إشعار المحاسب بوجود مستخلص مُفوتَر جاهز للمعالجة
            rec._completion_notify(
                body=_(
                    '<p>تم إنشاء فاتورة المستخلص <b>%s</b> وترحيلها — جاهزة للمعالجة المحاسبية.</p>'
                ) % (rec.name or ''),
                target_group_xmlid=_GROUP_ACCOUNTANT,
                activity_summary=_('فاتورة مستخلص جاهزة — %s') % (rec.name or ''),
            )
