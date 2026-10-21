from datetime import date, timedelta

from odoo import Command, api, fields, models

STATUS_SETTINGS = {"critical_days", "warning_days"}


class RenewalDocument(models.Model):
    _inherit = "renewal.document"

    @api.model
    def _cron_check_renewals(self):
        """The daily renewal_tracker cron also handles employee documents."""
        res = super()._cron_check_renewals()
        self.env["hr.employee"]._cron_employee_document_alerts()
        return res

    def _renewal_notify_users(self):
        ids = self.env["renewal.settings"].sudo()._get_settings().get("notify_user_ids") or []
        return self.env["res.users"].sudo().browse(ids).exists()

    def _create_renewal_activity(self, days_left, expired=False):
        """When notification users are set in the settings, every one of them gets the activity."""
        users = self._renewal_notify_users()
        if not users:
            return super()._create_renewal_activity(days_left, expired=expired)
        self.ensure_one()
        if expired:
            summary = f"وثيقة منتهية: {self.name}"
            note = f"انتهت صلاحية الوثيقة منذ {abs(days_left)} يوم. يرجى التجديد فوراً."
            deadline = date.today()
        else:
            summary = f"تجديد قريب: {self.name}"
            note = f"ستنتهي صلاحية الوثيقة خلال {days_left} يوم بتاريخ {self.expiry_date}."
            deadline = date.today() + timedelta(days=min(days_left, 3))
        for user in users:
            exists = self.env["mail.activity"].search_count([
                ("res_model", "=", "renewal.document"),
                ("res_id", "=", self.id),
                ("summary", "=", summary),
                ("user_id", "=", user.id),
            ], limit=1)
            if not exists:
                self.activity_schedule(
                    act_type_xmlid="mail.mail_activity_data_todo",
                    summary=summary,
                    note=note,
                    date_deadline=deadline,
                    user_id=user.id,
                )

    def _send_renewal_email(self, days_left):
        """When notification users are set in the settings, the e-mail goes to them."""
        partners = self._renewal_notify_users().partner_id.filtered("email")
        if not partners:
            return super()._send_renewal_email(days_left)
        self.ensure_one()
        template = self.env.ref("renewal_tracker.email_template_renewal_alert", raise_if_not_found=False)
        if template:
            template.with_context(days_left=days_left).send_mail(
                self.id, force_send=True,
                email_values={"recipient_ids": [Command.set(partners.ids)], "email_to": False},
            )


class RenewalSettings(models.Model):
    _inherit = "renewal.settings"

    access_user_ids = fields.Many2many(
        "res.users",
        string="المستخدمين المسموح لهم",
        compute="_compute_access_user_ids",
        inverse="_inverse_access_user_ids",
        domain=[("share", "=", False)],
        help="المستخدمين اللي يقدروا يفتحوا تطبيق متابعة التجديدات. "
             "مديرين النظام عندهم صلاحية دايماً.",
    )

    notify_user_ids = fields.Many2many(
        "res.users",
        "renewal_settings_notify_user_rel", "settings_id", "user_id",
        string="المستخدمين اللي هتوصلهم الإشعارات",
        domain=[("share", "=", False)],
        help="تنبيهات التجديد (Activity و/أو بريد) بتروح للمستخدمين دول. "
             "لو فاضي: بتروح للمسؤول عن الوثيقة / مدير الموظف زي الأول.",
    )

    @api.model
    def _get_settings(self):
        res = super()._get_settings()
        res["notify_user_ids"] = self.search([], limit=1).notify_user_ids.ids
        return res

    def _access_group(self):
        return self.env.ref("hr_employee_document_tracking.group_renewal_access").sudo()

    def _compute_access_user_ids(self):
        users = self._access_group().user_ids
        for rec in self:
            rec.access_user_ids = users

    def _inverse_access_user_ids(self):
        for rec in self[:1]:
            rec._access_group().write({"user_ids": [Command.set(rec.access_user_ids.ids)]})

    def write(self, vals):
        res = super().write(vals)
        if STATUS_SETTINGS & set(vals):
            self.env["hr.employee"]._recompute_document_status()
        return res
