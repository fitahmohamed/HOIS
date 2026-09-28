# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class RentInvoice(models.Model):
    """Rent Contract Invoices"""
    _name = 'rent.invoice'
    _description = 'Crete Invoice for Rented property'
    _rec_name = 'tenancy_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    tenancy_id = fields.Many2one('tenancy.details', string='Rent No.')
    customer_id = fields.Many2one(related='tenancy_id.tenancy_id',
                                  string='Customer', store=True)
    type = fields.Selection([('deposit', 'Deposit'),
                             ('rent', 'Rent'),
                             ('maintenance', 'Maintenance'),
                             ('penalty', 'Penalty'),
                             ('full_rent', 'Full Rent'),
                             ('other', 'Other')],
                            string='الدفعة', default='rent')
    invoice_date = fields.Date(string='تاريخ الاستحقاق')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency',
                                  related='company_id.currency_id',
                                  string='Currency')
    installment_type = fields.Selection(related="tenancy_id.type")

    # Calculation
    amount = fields.Monetary(string='المبلغ')
    rent_amount = fields.Monetary(string='مبلغ الإيجار')

    description = fields.Char(string='البيان', translate=True)
    rent_invoice_id = fields.Many2one('account.move', string='الفاتورة')
    rent_payment_id = fields.Many2one('account.payment', string='الدفعة')
    payment_state = fields.Selection(
        selection=[
            ('not_paid', 'غير مدفوع'),
            ('in_payment', 'جاري الدفع'),
            ('paid', 'مدفوع'),
            ('partial', 'مدفوع جزئياً'),
            ('reversed', 'ملغي'),
            ('invoicing_legacy', 'قديم'),
        ],
        compute='_compute_payment_state',
        inverse='_inverse_payment_state',
        string="حالة الدفع",
        store=True,
    )

    def _inverse_payment_state(self):
        """Allow direct write on payment_state"""
        pass
    landlord_id = fields.Many2one(related="tenancy_id.property_id.landlord_id",
                                  store=True)
    is_yearly = fields.Boolean()
    remain = fields.Integer()
    tenancy_type = fields.Selection(related="tenancy_id.type",
                                    string="Rent Type")
    service_amount = fields.Monetary(
        string="Extra Amount",
        help="Recurring Utility Service (if any) + Recurring Maintenance Service (if any)")
    is_extra_service = fields.Boolean(related="tenancy_id.is_extra_service")

    is_first_installment = fields.Boolean()
    service_days = fields.Integer()
    # Flag: commission already fully invoiced for this installment
    commission_invoice_id = fields.Many2one(
        'account.move', string='فاتورة العمولة', readonly=True)
    commission_remaining_ok = fields.Boolean(
        compute='_compute_commission_remaining_ok',
        help='True when no more commission is due on the contract')

    @api.depends('rent_payment_id', 'rent_payment_id.state',
                 'rent_invoice_id', 'rent_invoice_id.payment_state')
    def _compute_payment_state(self):
        """حالة الدفع: من الـ payment لو commission، من الفاتورة لو ownership"""
        state_map = {'draft': 'not_paid', 'posted': 'paid', 'cancel': 'reversed'}
        for rec in self:
            if rec.rent_payment_id:
                rec.payment_state = state_map.get(rec.rent_payment_id.state, 'not_paid')
            elif rec.rent_invoice_id:
                rec.payment_state = rec.rent_invoice_id.payment_state or 'not_paid'
            else:
                rec.payment_state = 'not_paid'

    @api.depends('commission_invoice_id', 'tenancy_id.commission_per_installment')
    def _compute_commission_remaining_ok(self):
        for rec in self:
            # الزرار يختفي لو: فيه فاتورة عمولة لهذا القسط، أو لا يوجد عمولة محددة
            if not rec.tenancy_id.commission_per_installment:
                rec.commission_remaining_ok = True
            elif rec.commission_invoice_id:
                rec.commission_remaining_ok = True
            else:
                rec.commission_remaining_ok = False

    def action_create_commission_invoice(self):
        """Create commission invoice to landlord for this installment"""
        self.ensure_one()
        tenancy = self.tenancy_id
        if not tenancy.commission_per_installment:
            raise UserError(_('من فضلك حدد إجمالي قيمة العمولة في العقد أولاً.'))
        if self.commission_invoice_id:
            raise UserError(_('تم إنشاء فاتورة العمولة لهذا القسط مسبقاً.'))
        if tenancy.commission_remaining <= 0:
            return {'type': 'ir.actions.act_window_close'}  # اختفي بصمت

        commission_amount = tenancy.commission_remaining
        landlord = tenancy.property_landlord_id
        if not landlord:
            raise UserError(_('لا يوجد مالك محدد على العقار.'))

        commission_item = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.account_installment_item_id')
        product = (self.env['product.product'].browse(int(commission_item))
                   if commission_item else False)

        invoice_vals = {
            'move_type': 'out_invoice',   # فاتورة مبيعات — بتبيع خدمة السمسرة للمالك
            'partner_id': landlord.id,
            'invoice_date': fields.Date.today(),
            'tenancy_commission_id': tenancy.id,   # يربطها بـ commission_invoice_ids
            'ref': _('عمولة سمسرة | %s') % (tenancy.tenancy_seq or ''),
            'invoice_line_ids': [(0, 0, {
                'name': _('عمولة إيجار – %s – %s') % (
                    tenancy.property_id.name or '',
                    self.description or str(self.invoice_date or '')),
                'quantity': 1,
                'price_unit': commission_amount,
                'product_id': product.id if product else False,
            })],
        }
        invoice = self.env['account.move'].sudo().create(invoice_vals)
        # اربط الفاتورة بهذا القسط عشان مش يتعمل تاني
        self.commission_invoice_id = invoice.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('فاتورة العمولة'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def unlink(self):
        """Block deletion of installments that have a confirmed payment"""
        for rec in self:
            if rec.rent_payment_id and rec.rent_payment_id.state == 'posted':
                if not self.env.user.has_group('account.group_account_manager'):
                    raise UserError(_(
                        'You cannot delete installment "%s" because its payment receipt is '
                        'already confirmed. Contact an Accounting Manager to proceed.',
                        rec.description or rec.tenancy_id.tenancy_seq
                    ))
        return super().unlink()

    def action_create_invoice(self):
        """إنشاء فاتورة أو سند قبض حسب نوع الإيجار"""
        if self.tenancy_id.rental_type == 'ownership':
            # مسار ملكية: فاتورة عادية
            self._process_manual_ownership_invoice()
        elif self.tenancy_id.rent_unit == 'Day':
            self._process_manual_daily_invoice()
        else:
            self._process_manual_invoice()
        if (self.tenancy_id.is_maintenance_service
                and self.tenancy_id.maintenance_service_invoice == 'separate'):
            self._process_separate_invoices(maintenance=True)
        if self.tenancy_id.is_extra_service and self.tenancy_id.extra_service_invoice == 'separate':
            self._process_separate_invoices(utility=True)

    def _process_manual_ownership_invoice(self):
        """مسار ملكية: ينشئ فاتورة مبيعات عادية"""
        invoice_post_type = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.invoice_post_type')
        service_quantity = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.quarterly_service_quantity')
        quarterly_service_quantity = int(service_quantity) if service_quantity else 1
        service_half_year = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.half_yearly_service_quantity')
        half_yearly_service_quantity = int(service_half_year) if service_half_year else 1

        invoice_lines = []
        amount = self.amount
        if self.tenancy_id.is_extra_service and self.tenancy_id.extra_service_invoice == 'merge':
            if self.tenancy_id.payment_term in ['monthly', 'half_year']:
                for line in self.tenancy_id.extra_services_ids.filtered(
                        lambda l: l.service_type == 'monthly'):
                    qty = half_yearly_service_quantity if self.tenancy_id.payment_term == 'half_year' else 1
                    invoice_lines.append((0, 0, {
                        'product_id': line.service_id.id,
                        'name': 'خدمة متكررة – ' + line.service_id.name,
                        'quantity': qty, 'price_unit': line.price,
                        'tax_ids': self.tenancy_id.tax_ids.ids if self.tenancy_id.service_tax else False
                    }))
            elif self.tenancy_id.payment_term == 'quarterly':
                for line in self.tenancy_id.extra_services_ids.filtered(
                        lambda l: l.service_type == 'monthly'):
                    invoice_lines.append((0, 0, {
                        'product_id': line.service_id.id,
                        'name': 'خدمة متكررة – ' + line.service_id.name,
                        'quantity': quarterly_service_quantity, 'price_unit': line.price,
                        'tax_ids': self.tenancy_id.tax_ids.ids if self.tenancy_id.service_tax else False
                    }))
        if (self.tenancy_id.is_maintenance_service
                and self.tenancy_id.maintenance_rent_type == 'recurring'
                and self.tenancy_id.maintenance_service_invoice == 'merge'):
            invoice_lines.append((0, 0, {
                'product_id': self.tenancy_id.maintenance_item_id.id,
                'name': 'صيانة متكررة – ' + self.tenancy_id.property_id.name,
                'quantity': 1, 'price_unit': self.tenancy_id.total_maintenance,
                'tax_ids': self.tenancy_id.tax_ids.ids if self.tenancy_id.instalment_tax else False
            }))
        invoice_lines.insert(0, (0, 0, {
            'product_id': self.tenancy_id.installment_item_id.id,
            'name': self.description,
            'quantity': 1, 'price_unit': self.amount,
            'tax_ids': self.tenancy_id.tax_ids.ids if self.tenancy_id.instalment_tax else False
        }))
        invoice_id = self.env['account.move'].create({
            'partner_id': self.customer_id.id,
            'move_type': 'out_invoice',
            'invoice_date': self.invoice_date,
            'tenancy_id': self.tenancy_id.id,
            'invoice_line_ids': invoice_lines,
        })
        self.service_amount = max(0.0, invoice_id.amount_total - self.amount)
        if invoice_post_type == 'automatically':
            invoice_id.action_post()
        self.rent_invoice_id = invoice_id.id
        self.tenancy_id.action_send_tenancy_reminder()

    def _process_manual_invoice(self):
        """Process Manual Payment : Monthly, Quarterly, Yearly - payment receipt only, no invoice"""
        service_quantity = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.quarterly_service_quantity')
        quarterly_service_quantity = int(service_quantity) if service_quantity else 1

        service_half_year = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.half_yearly_service_quantity')
        half_yearly_service_quantity = int(service_half_year) if service_half_year else 1

        # Calculate total amount (installment + merged services + merged maintenance)
        total_amount = self.amount
        if self.tenancy_id.is_extra_service and self.tenancy_id.extra_service_invoice == 'merge':
            if self.tenancy_id.payment_term in ["monthly", "half_year"]:
                for line in self.tenancy_id.extra_services_ids:
                    if line.service_type == "monthly":
                        qty = half_yearly_service_quantity if self.tenancy_id.payment_term == 'half_year' else 1
                        total_amount += line.price * qty
            elif self.tenancy_id.payment_term == "quarterly":
                for line in self.tenancy_id.extra_services_ids:
                    if line.service_type == "monthly":
                        total_amount += line.price * (self.remain if self.remain > 0 else 3)
            elif self.tenancy_id.payment_term == "year":
                for line in self.tenancy_id.extra_services_ids:
                    if line.service_type == "monthly":
                        total_amount += line.price * 12
        if (self.tenancy_id.is_maintenance_service
                and self.tenancy_id.maintenance_rent_type == 'recurring'
                and self.tenancy_id.maintenance_service_invoice == 'merge'):
            maint_qty = 1
            if self.tenancy_id.payment_term == 'quarterly':
                maint_qty = quarterly_service_quantity
            elif self.tenancy_id.payment_term == 'half_year':
                maint_qty = half_yearly_service_quantity
            total_amount += self.tenancy_id.total_maintenance * maint_qty

        self.service_amount = (total_amount - self.amount) if total_amount > self.amount else 0.0

        # Create payment receipt only (no invoice)
        payment = self.tenancy_id._create_tenant_payment(
            rec=self.tenancy_id,
            amount=total_amount,
            payment_date=self.invoice_date,
            description=self.description or ('Installment of ' + self.tenancy_id.property_id.name),
        )
        self.rent_payment_id = payment.id
        self.tenancy_id.action_send_tenancy_reminder()

    def _process_manual_daily_invoice(self):
        """Process Daily Payment : payment receipt only, no invoice"""
        # Calculate total amount (daily installment + merged services + merged maintenance)
        total_amount = self.amount
        if self.tenancy_id.is_extra_service and self.tenancy_id.extra_service_invoice == 'merge':
            for line in self.tenancy_id.extra_services_ids.filtered(
                    lambda l: l.service_type == 'monthly'):
                total_amount += line.price * self.service_days
        if (self.tenancy_id.is_maintenance_service
                and self.tenancy_id.maintenance_rent_type == 'recurring'
                and self.tenancy_id.maintenance_service_invoice == 'merge'):
            total_amount += self.tenancy_id.total_maintenance * self.service_days

        self.service_amount = (total_amount - self.amount) if total_amount > self.amount else 0.0

        # Create payment receipt only (no invoice)
        payment = self.tenancy_id._create_tenant_payment(
            rec=self.tenancy_id,
            amount=total_amount,
            payment_date=self.invoice_date,
            description=self.description or ('Daily Installment of ' + self.tenancy_id.property_id.name),
        )
        self.rent_payment_id = payment.id
        self.tenancy_id.action_send_tenancy_reminder()

    def _process_separate_invoices(self, maintenance=None, utility=None):
        """Process Utility and Maintenance Separate Invoices"""
        qty = 1
        service_quantity = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.quarterly_service_quantity')
        quarterly_service_quantity = int(service_quantity) if service_quantity else 1

        service_half_year = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.half_yearly_service_quantity')
        half_yearly_service_quantity = int(service_half_year) if service_half_year else 1

        if self.tenancy_id.rent_unit == 'Day':
            qty = self.service_days
        else:
            if self.tenancy_id.payment_term == 'quarterly':
                qty = quarterly_service_quantity
            elif self.tenancy_id.payment_term == 'half_year':
                qty = half_yearly_service_quantity
        if maintenance:
            maintenance_invoice_id = self.env['account.move'].create({
                "partner_id": self.tenancy_id.tenancy_id.id,
                "move_type": "out_invoice",
                "invoice_date": self.invoice_date,
                "tenancy_id": self.tenancy_id.id,
                "invoice_line_ids": [(0, 0, {
                    "product_id": self.tenancy_id.maintenance_item_id.id,
                    "name": "Recurring Maintenance of " + self.tenancy_id.property_id.name,
                    "quantity": qty,
                    "price_unit": self.tenancy_id.total_maintenance,
                })],
            })
            self.env['rent.invoice'].create({
                "tenancy_id": self.tenancy_id.id,
                "type": "maintenance",
                "invoice_date": self.invoice_date,
                "amount": maintenance_invoice_id.amount_total,
                "description": "Recurring Maintenance of " + self.tenancy_id.property_id.name,
                "rent_invoice_id": maintenance_invoice_id.id})
        if utility:
            service_invoice_lines = []
            for line in self.tenancy_id.extra_services_ids.filtered(
                    lambda line: line.service_type == 'monthly'):
                service_invoice_lines.append((0, 0, {
                    "product_id": line.service_id.id,
                    "name": f"Service Type : Recurring - {line.service_id.name}",
                    "quantity": qty,
                    "price_unit": line.price,
                    "tax_ids": self.tenancy_id.tax_ids.ids if self.tenancy_id.service_tax else False
                }))
            service_invoice_id = self.env['account.move'].create({
                "partner_id": self.tenancy_id.tenancy_id.id,
                "move_type": "out_invoice",
                "invoice_date": self.invoice_date,
                "tenancy_id": self.tenancy_id.id,
                "invoice_line_ids": service_invoice_lines,
            })
            self.env['rent.invoice'].create({
                "tenancy_id": self.tenancy_id.id,
                "type": "other",
                "invoice_date": self.invoice_date,
                "amount": service_invoice_id.amount_total,
                "description": "Recurring Utility Services",
                "rent_invoice_id": service_invoice_id.id})


class TenancyInvoice(models.Model):
    """Tenancy account move"""
    _inherit = 'account.move'

    tenancy_id = fields.Many2one('tenancy.details',
                                 readonly=True,
                                 string="رقم العقد",
                                 store=True)
    sold_id = fields.Many2one('property.vendor',
                              string="Sold Information",
                              readonly=True,
                              store=True)
    tenancy_property_id = fields.Many2one(related="tenancy_id.property_id",
                                          string="الوحدة / العقار", store=True)
    sold_property_id = fields.Many2one(related="sold_id.property_id",
                                       string="Property ")
    maintenance_request_id = fields.Many2one(
        'maintenance.request', string="Maintenance Ref.")
    penalty_id = fields.Many2one('penalty.invoice', readonly=True)
    show_in_owner_report = fields.Boolean(
        string="يظهر في تقرير المالك",
        default=True,
        help="لو مفعّل، القيد ده هيظهر في تقرير المالك (كشف الحساب)")
    is_sale_installed = fields.Boolean()
    is_exact_move_duplicate = fields.Boolean(
        string="Is Exact Duplicate",
        compute='_compute_is_exact_move_duplicate',
        store=True,
        copy=False,
    )
    is_draft_duplicated_ref_ids = fields.Boolean(
        string="Is Draft Duplicate",
        compute='_compute_is_exact_move_duplicate',
        store=True,
        copy=False,
    )

    @api.depends('name')
    def _compute_is_exact_move_duplicate(self):
        for move in self:
            move.is_exact_move_duplicate = False
            move.is_draft_duplicated_ref_ids = False

    def action_delete_duplicates(self):
        for move in self:
            draft_duplicates = move.duplicated_ref_ids.filtered(
                lambda duplicate: duplicate.state == 'draft'
            )
            if not draft_duplicates:
                raise UserError(_("There are no draft duplicate documents to delete."))
            draft_duplicates.unlink()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    # Commission invoice link
    tenancy_commission_id = fields.Many2one(
        'tenancy.details',
        string='عقد العمولة',
        readonly=True, store=True)
    tenancy_commission_property_id = fields.Many2one(
        related='tenancy_commission_id.property_id',
        string='الوحدة', store=True)
    tenancy_commission_landlord_id = fields.Many2one(
        related='tenancy_commission_id.property_landlord_id',
        string='المالك', store=True)
    tenancy_commission_tenant_id = fields.Many2one(
        related='tenancy_commission_id.tenancy_id',
        string='المستأجر', store=True)

    # Auto journal entry link (rent collection / commission)
    tenancy_journal_id = fields.Many2one(
        'tenancy.details',
        string='عقد القيد',
        readonly=True, store=True)
    tenancy_journal_property_id = fields.Many2one(
        related='tenancy_journal_id.property_id',
        string='الوحدة', store=True)
    tenancy_journal_landlord_id = fields.Many2one(
        related='tenancy_journal_id.property_landlord_id',
        string='المالك', store=True)
    tenancy_journal_tenant_id = fields.Many2one(
        related='tenancy_journal_id.tenancy_id',
        string='المستأجر', store=True)
    tenancy_journal_seq = fields.Char(
        related='tenancy_journal_id.tenancy_seq',
        string='رقم العقد', store=True)

    def action_post(self):
        """Override action_post to auto-create commission journal entry"""
        res = super().action_post()
        for move in self.filtered(lambda m: m.tenancy_commission_id):
            move._create_commission_journal_entry()
        return res

    def _create_commission_journal_entry(self):
        """
        قيد أوتوماتيك عند تأكيد فاتورة عمولة المبيعات:
          DR  حساب المالك الدائن (من الإعدادات)  — يخصم من مستحقات المالك
          CR  حساب العملاء من الفاتورة           — يغلق الفاتورة ويجعل حالتها مدفوعة
        """
        self.ensure_one()
        tenancy = self.tenancy_commission_id
        if not tenancy:
            return

        landlord_account_id = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'rental_management.landlord_account_id') or 0)
        if not landlord_account_id:
            return

        landlord_account = self.env['account.account'].browse(landlord_account_id)
        if not landlord_account.exists():
            return

        landlord = tenancy.property_landlord_id

        # سطر العملاء المفتوح في فاتورة المبيعات (out_invoice → asset_receivable)
        receivable_line = self.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
            and not l.reconciled
        )[:1]

        if receivable_line:
            receivable_account = receivable_line.account_id
        else:
            receivable_account = (
                landlord.property_account_receivable_id or
                self.env['account.account'].search([
                    ('account_type', '=', 'asset_receivable'),
                    ('company_id', '=', self.company_id.id),
                    ('deprecated', '=', False)], limit=1))

        if not receivable_account:
            return

        # دفتر يومية العمولة من الإعدادات
        journal_param = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.commission_journal_id')
        if journal_param and int(journal_param or 0):
            journal = self.env['account.journal'].browse(int(journal_param))
        else:
            journal = self.env['account.journal'].search(
                [('type', '=', 'general'),
                 ('company_id', '=', self.company_id.id)], limit=1)
        if not journal:
            return

        amount = self.amount_total

        move_vals = {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.invoice_date or fields.Date.today(),
            'ref': _('عمولة سمسرة | %s | %s') % (
                tenancy.tenancy_seq or '', tenancy.property_id.name or ''),
            'tenancy_journal_id': tenancy.id,
            'line_ids': [
                # DR حساب المالك الدائن — يخصم من مستحقاته
                (0, 0, {
                    'account_id': landlord_account.id,
                    'partner_id': landlord.id if landlord else False,
                    'name': _('خصم عمولة السمسار من مستحقات المالك – %s') % (
                        tenancy.tenancy_seq or ''),
                    'debit': amount,
                    'credit': 0.0,
                }),
                # CR حساب العملاء — يغلق فاتورة المبيعات
                (0, 0, {
                    'account_id': receivable_account.id,
                    'partner_id': landlord.id if landlord else False,
                    'name': _('سداد عمولة سمسرة – %s') % (
                        tenancy.tenancy_seq or ''),
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }
        entry = self.env['account.move'].sudo().create(move_vals)
        entry.action_post()

        # مطابقة مع الفاتورة لتغيير حالتها لـ مدفوعة
        if receivable_line:
            credit_line = entry.line_ids.filtered(
                lambda l: l.account_id == receivable_account and l.credit > 0)[:1]
            if credit_line:
                (receivable_line + credit_line).reconcile()
