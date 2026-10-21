from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class RenewalDocument(models.Model):
    _name = 'renewal.document'
    _description = 'وثيقة تجديد'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc'
    _rec_name = 'name'

    name = fields.Char(
        string='اسم الوثيقة',
        required=True,
        tracking=True,
    )
    document_type = fields.Selection([
        ('car_license', 'رخصة سيارة'),
        ('employee_doc', 'وثيقة موظف'),
        ('other', 'أخرى'),
    ], string='نوع الوثيقة', required=True, default='car_license', tracking=True)

    reference = fields.Char(string='رقم المرجع / اللوحة', tracking=True)
    responsible_id = fields.Many2one(
        'res.users', string='المسؤول',
        default=lambda self: self.env.user,
        tracking=True,
    )
    start_date = fields.Date(string='تاريخ البداية', tracking=True)
    expiry_date = fields.Date(string='تاريخ الانتهاء', required=True, tracking=True)
    notes = fields.Text(string='ملاحظات')

    days_remaining = fields.Integer(
        string='الأيام المتبقية',
        compute='_compute_days_remaining',
        store=True,
    )
    status = fields.Selection([
        ('expired', 'منتهي'),
        ('critical', 'عاجل جداً'),
        ('warning', 'قريب'),
        ('ok', 'سليم'),
    ], string='الحالة', compute='_compute_status', store=True)

    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color', compute='_compute_color')

    renewal_history_ids = fields.One2many(
        'renewal.document.history', 'document_id',
        string='سجل التجديدات',
    )
    renewal_count = fields.Integer(
        string='عدد التجديدات',
        compute='_compute_renewal_count',
    )

    @api.depends('expiry_date')
    def _compute_days_remaining(self):
        today = date.today()
        for rec in self:
            if rec.expiry_date:
                rec.days_remaining = (rec.expiry_date - today).days
            else:
                rec.days_remaining = 0

    @api.depends('days_remaining')
    def _compute_status(self):
        settings = self.env['renewal.settings'].sudo()._get_settings()
        critical_days = settings.get('critical_days', 7)
        warning_days = settings.get('warning_days', 30)
        for rec in self:
            d = rec.days_remaining
            if d < 0:
                rec.status = 'expired'
            elif d <= critical_days:
                rec.status = 'critical'
            elif d <= warning_days:
                rec.status = 'warning'
            else:
                rec.status = 'ok'

    @api.depends('status')
    def _compute_color(self):
        color_map = {'expired': 1, 'critical': 2, 'warning': 3, 'ok': 10}
        for rec in self:
            rec.color = color_map.get(rec.status, 10)

    @api.depends('renewal_history_ids')
    def _compute_renewal_count(self):
        for rec in self:
            rec.renewal_count = len(rec.renewal_history_ids)

    def action_renew(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'تجديد الوثيقة',
            'res_model': 'renewal.document.renew.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_id': self.id,
                'default_old_expiry_date': self.expiry_date,
            },
        }

    def action_view_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'سجل التجديدات',
            'res_model': 'renewal.document.history',
            'view_mode': 'list,form',
            'domain': [('document_id', '=', self.id)],
        }

    @api.model
    def _cron_check_renewals(self):
        """Cron job يشتغل يومياً للتحقق من مواعيد التجديد"""
        settings_obj = self.env['renewal.settings'].sudo()
        settings = settings_obj._get_settings()
        alert_levels = settings.get('alert_levels', [30, 14, 7, 1])
        notify_activity = settings.get('notify_activity', True)
        notify_email = settings.get('notify_email', False)

        today = date.today()
        documents = self.search([('active', '=', True), ('expiry_date', '>=', today)])

        for doc in documents:
            days_left = doc.days_remaining
            if days_left in alert_levels:
                if notify_activity:
                    doc._create_renewal_activity(days_left)
                if notify_email:
                    doc._send_renewal_email(days_left)
                _logger.info(
                    'تنبيه تجديد: %s - باقي %s يوم', doc.name, days_left
                )

        # تنبيه للوثائق المنتهية
        expired = self.search([('active', '=', True), ('expiry_date', '<', today)])
        for doc in expired:
            existing = self.env['mail.activity'].search([
                ('res_model', '=', 'renewal.document'),
                ('res_id', '=', doc.id),
                ('activity_type_id.category', '=', 'default'),
                ('note', 'ilike', 'منتهي'),
            ], limit=1)
            if not existing:
                doc._create_renewal_activity(doc.days_remaining, expired=True)

    def _create_renewal_activity(self, days_left, expired=False):
        self.ensure_one()
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search([], limit=1)
        if not activity_type:
            return

        if expired:
            summary = f'وثيقة منتهية: {self.name}'
            note = f'انتهت صلاحية الوثيقة منذ {abs(days_left)} يوم. يرجى التجديد فوراً.'
            deadline = date.today()
        else:
            summary = f'تجديد قريب: {self.name}'
            note = f'ستنتهي صلاحية الوثيقة خلال {days_left} يوم بتاريخ {self.expiry_date}.'
            deadline = date.today() + timedelta(days=min(days_left, 3))

        existing = self.env['mail.activity'].search([
            ('res_model', '=', 'renewal.document'),
            ('res_id', '=', self.id),
            ('summary', '=', summary),
        ], limit=1)
        if existing:
            return

        self.activity_schedule(
            activity_type_id=activity_type.id,
            summary=summary,
            note=note,
            date_deadline=deadline,
            user_id=self.responsible_id.id or self.env.user.id,
        )

    def _send_renewal_email(self, days_left):
        self.ensure_one()
        recipient_email = self.responsible_id.email or self.responsible_id.partner_id.email
        if not self.responsible_id or not recipient_email:
            return
        template = self.env.ref(
            'renewal_tracker.email_template_renewal_alert',
            raise_if_not_found=False,
        )
        if template:
            template.with_context(days_left=days_left).send_mail(self.id, force_send=True)


class RenewalDocumentHistory(models.Model):
    _name = 'renewal.document.history'
    _description = 'سجل تجديدات الوثيقة'
    _order = 'renewal_date desc'

    document_id = fields.Many2one('renewal.document', string='الوثيقة', required=True, ondelete='cascade')
    renewal_date = fields.Date(string='تاريخ التجديد', default=fields.Date.today, required=True)
    old_expiry_date = fields.Date(string='تاريخ الانتهاء القديم')
    new_expiry_date = fields.Date(string='تاريخ الانتهاء الجديد', required=True)
    renewed_by = fields.Many2one('res.users', string='جدده', default=lambda self: self.env.user)
    notes = fields.Text(string='ملاحظات')


class RenewalDocumentRenewWizard(models.TransientModel):
    _name = 'renewal.document.renew.wizard'
    _description = 'معالج تجديد الوثيقة'

    document_id = fields.Many2one('renewal.document', string='الوثيقة', required=True)
    old_expiry_date = fields.Date(string='تاريخ الانتهاء الحالي', readonly=True)
    new_start_date = fields.Date(string='تاريخ البداية الجديد')
    new_expiry_date = fields.Date(string='تاريخ الانتهاء الجديد', required=True)
    notes = fields.Text(string='ملاحظات')

    def action_confirm_renew(self):
        self.ensure_one()
        if self.new_expiry_date <= (self.old_expiry_date or date.today()):
            raise UserError('تاريخ الانتهاء الجديد يجب أن يكون بعد التاريخ الحالي.')

        doc = self.document_id
        self.env['renewal.document.history'].create({
            'document_id': doc.id,
            'renewal_date': date.today(),
            'old_expiry_date': doc.expiry_date,
            'new_expiry_date': self.new_expiry_date,
            'renewed_by': self.env.user.id,
            'notes': self.notes,
        })

        doc.write({
            'expiry_date': self.new_expiry_date,
            'start_date': self.new_start_date or doc.start_date,
        })

        # إلغاء الأنشطة القديمة
        old_activities = self.env['mail.activity'].search([
            ('res_model', '=', 'renewal.document'),
            ('res_id', '=', doc.id),
        ])
        old_activities.action_done()

        doc.message_post(
            body=f'تم تجديد الوثيقة. تاريخ الانتهاء الجديد: {self.new_expiry_date}',
            message_type='comment',
        )
        return {'type': 'ir.actions.act_window_close'}
