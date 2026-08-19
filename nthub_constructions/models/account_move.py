# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _cron_schedule_vendor_bill_due_reminders(self):
        reminder_date = fields.Date.context_today(self) + relativedelta(days=2)
        bills = self.search([
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'reversed')),
            ('invoice_date_due', '=', reminder_date),
        ])
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        accountant_group = self.env.ref('account.group_account_user', raise_if_not_found=False)
        users = accountant_group.users if accountant_group else self.env['res.users']
        summary = _('Vendor Bill Due Reminder')

        for bill in bills:
            for user in users.filtered(lambda usr: not usr.share):
                existing_activity = self.env['mail.activity'].search([
                    ('res_model', '=', bill._name),
                    ('res_id', '=', bill.id),
                    ('activity_type_id', '=', activity_type.id),
                    ('user_id', '=', user.id),
                    ('summary', '=', summary),
                ], limit=1)
                if existing_activity:
                    continue
                bill.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    date_deadline=fields.Date.context_today(self),
                    summary=summary,
                    note=_('Vendor bill %s is due on %s.') % (bill.name, bill.invoice_date_due),
                )
