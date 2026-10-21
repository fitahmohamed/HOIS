from odoo import _, api, fields, models

from datetime import timedelta

from .document_common import DOC_TYPES, LICENSE_TYPES, STATUS_SELECTION, compute_days, get_status

PREFIXES = ("passport", "iqama", "license", "driver_card", "medical")

HR = "hr.group_hr_user"


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # ------------------------------------------------------------------ Passport
    passport_number = fields.Char(string="Passport Number", groups=HR, tracking=True)
    passport_country_id = fields.Many2one("res.country", string="Passport Issue Country", groups=HR)
    passport_file = fields.Binary(string="Passport File", attachment=True, groups=HR)
    passport_file_name = fields.Char(groups=HR)
    passport_note = fields.Text(string="Passport Note", groups=HR)
    passport_status = fields.Selection(
        STATUS_SELECTION, string="Passport Status", compute="_compute_doc_status", store=True, groups=HR)
    passport_issue_date = fields.Date(string="Passport Issue Date", groups=HR)
    passport_expiry_date = fields.Date(string="Passport Expiry Date", groups=HR, tracking=True)
    passport_remaining_days = fields.Integer(
        string="Passport Remaining Days", compute="_compute_doc_remaining_days", store=True, groups=HR)
    passport_history_ids = fields.One2many(
        "hr.employee.document.history", "employee_id", domain=[("doc_type", "=", "passport")],
        string="Passport History", groups=HR)

    # ------------------------------------------------------------------ Iqama
    iqama_number = fields.Char(string="Iqama Number", groups=HR, tracking=True)
    iqama_profession = fields.Char(string="Iqama Profession", groups=HR)
    iqama_sponsor = fields.Char(string="Iqama Sponsor", groups=HR)
    iqama_country_id = fields.Many2one("res.country", string="Iqama Issue Country", groups=HR)
    iqama_file = fields.Binary(string="Iqama File", attachment=True, groups=HR)
    iqama_file_name = fields.Char(groups=HR)
    iqama_note = fields.Text(string="Iqama Note", groups=HR)
    iqama_status = fields.Selection(
        STATUS_SELECTION, string="Iqama Status", compute="_compute_doc_status", store=True, groups=HR)
    iqama_issue_date = fields.Date(string="Iqama Issue Date", groups=HR)
    iqama_expiry_date = fields.Date(string="Iqama Expiry Date", groups=HR, tracking=True)
    iqama_remaining_days = fields.Integer(
        string="Iqama Remaining Days", compute="_compute_doc_remaining_days", store=True, groups=HR)
    iqama_history_ids = fields.One2many(
        "hr.employee.document.history", "employee_id", domain=[("doc_type", "=", "iqama")],
        string="Iqama History", groups=HR)

    # ------------------------------------------------------------------ Driving License
    license_number = fields.Char(string="License Number", groups=HR, tracking=True)
    license_type = fields.Selection(LICENSE_TYPES, string="License Type", groups=HR)
    license_authority = fields.Char(string="License Authority", groups=HR)
    license_file = fields.Binary(string="License File", attachment=True, groups=HR)
    license_file_name = fields.Char(groups=HR)
    license_note = fields.Text(string="License Note", groups=HR)
    license_status = fields.Selection(
        STATUS_SELECTION, string="License Status", compute="_compute_doc_status", store=True, groups=HR)
    license_issue_date = fields.Date(string="License Issue Date", groups=HR)
    license_expiry_date = fields.Date(string="License Expiry Date", groups=HR, tracking=True)
    license_remaining_days = fields.Integer(
        string="License Remaining Days", compute="_compute_doc_remaining_days", store=True, groups=HR)
    license_history_ids = fields.One2many(
        "hr.employee.document.history", "employee_id", domain=[("doc_type", "=", "license")],
        string="Driving License History", groups=HR)

    # ------------------------------------------------------------------ Driver Card
    driver_card_number = fields.Char(string="Driver Card Number", groups=HR, tracking=True)
    driver_card_file = fields.Binary(string="Driver Card File", attachment=True, groups=HR)
    driver_card_file_name = fields.Char(groups=HR)
    driver_card_note = fields.Text(string="Driver Card Note", groups=HR)
    driver_card_status = fields.Selection(
        STATUS_SELECTION, string="Driver Card Status", compute="_compute_doc_status", store=True, groups=HR)
    driver_card_issue_date = fields.Date(string="Driver Card Issue Date", groups=HR)
    driver_card_expiry_date = fields.Date(string="Driver Card Expiry Date", groups=HR, tracking=True)
    driver_card_remaining_days = fields.Integer(
        string="Driver Card Remaining Days", compute="_compute_doc_remaining_days", store=True, groups=HR)
    driver_card_history_ids = fields.One2many(
        "hr.employee.document.history", "employee_id", domain=[("doc_type", "=", "driver_card")],
        string="Driver Card History", groups=HR)

    # ------------------------------------------------------------------ Medical Insurance
    medical_policy_number = fields.Char(string="Policy Number", groups=HR, tracking=True)
    medical_company = fields.Char(string="Insurance Company", groups=HR)
    medical_membership_number = fields.Char(string="Membership Number", groups=HR)
    medical_type = fields.Char(string="Insurance Type", groups=HR)
    medical_file = fields.Binary(string="Medical Insurance File", attachment=True, groups=HR)
    medical_file_name = fields.Char(groups=HR)
    medical_note = fields.Text(string="Medical Insurance Note", groups=HR)
    medical_status = fields.Selection(
        STATUS_SELECTION, string="Medical Insurance Status", compute="_compute_doc_status", store=True, groups=HR)
    medical_issue_date = fields.Date(string="Medical Insurance Issue Date", groups=HR)
    medical_expiry_date = fields.Date(string="Medical Insurance Expiry Date", groups=HR, tracking=True)
    medical_remaining_days = fields.Integer(
        string="Medical Insurance Remaining Days", compute="_compute_doc_remaining_days", store=True, groups=HR)
    medical_history_ids = fields.One2many(
        "hr.employee.document.history", "employee_id", domain=[("doc_type", "=", "medical")],
        string="Medical Insurance History", groups=HR)

    # ------------------------------------------------------------------ All history (smart button)
    document_history_ids = fields.One2many(
        "hr.employee.document.history", "employee_id", string="Renewal History", groups=HR)
    document_history_count = fields.Integer(compute="_compute_document_history_count", groups=HR)

    @api.depends(
        "passport_issue_date", "passport_expiry_date",
        "iqama_issue_date", "iqama_expiry_date",
        "license_issue_date", "license_expiry_date",
        "driver_card_issue_date", "driver_card_expiry_date",
        "medical_issue_date", "medical_expiry_date",
    )
    def _compute_doc_remaining_days(self):
        for emp in self:
            for prefix in PREFIXES:
                emp[f"{prefix}_remaining_days"] = compute_days(
                    emp[f"{prefix}_issue_date"], emp[f"{prefix}_expiry_date"]
                )

    # ------------------------------------------------------------------ Automatic status
    @api.depends(
        "passport_expiry_date", "iqama_expiry_date", "license_expiry_date",
        "driver_card_expiry_date", "medical_expiry_date",
    )
    def _compute_doc_status(self):
        settings = self.env["renewal.settings"].sudo()._get_settings()
        today = fields.Date.today()
        for emp in self:
            for prefix in PREFIXES:
                emp[f"{prefix}_status"] = get_status(emp[f"{prefix}_expiry_date"], settings, today)

    @api.model
    def _recompute_document_status(self):
        """Statuses depend on today's date and on the settings: recompute them."""
        domain = ["|"] * (len(PREFIXES) - 1) + [(f"{p}_expiry_date", "!=", False) for p in PREFIXES]
        employees = self.sudo().with_context(active_test=False).search(domain)
        fnames = [f"{p}_status" for p in PREFIXES]
        for fname in fnames:
            self.env.add_to_compute(self._fields[fname], employees)
        employees._recompute_recordset(fnames)
        self.env["hr.employee.document.history"]._recompute_document_status()

    # ------------------------------------------------------------------ Alerts (renewal_tracker settings)
    @api.model
    def _cron_employee_document_alerts(self):
        self._recompute_document_status()
        settings = self.env["renewal.settings"].sudo()._get_settings()
        alert_levels = settings.get("alert_levels", [30, 14, 7, 1])
        today = fields.Date.today()
        labels = dict(DOC_TYPES)
        domain = ["|"] * (len(PREFIXES) - 1) + [(f"{p}_expiry_date", "!=", False) for p in PREFIXES]
        for emp in self.sudo().search(domain):
            for prefix in PREFIXES:
                expiry = emp[f"{prefix}_expiry_date"]
                if not expiry:
                    continue
                days_left = (expiry - today).days
                if days_left < 0:
                    emp._document_alert(prefix, labels[prefix], days_left, expiry, settings, expired=True)
                elif days_left in alert_levels:
                    emp._document_alert(prefix, labels[prefix], days_left, expiry, settings)

    def _document_alert_summaries(self, label):
        return (f"تجديد قريب: {label}", f"وثيقة منتهية: {label}")

    def _document_responsible_user(self, prefix):
        self.ensure_one()
        if self.parent_id.user_id:
            return self.parent_id.user_id
        last = self.env["hr.employee.document.history"].sudo().search(
            [("employee_id", "=", self.id), ("doc_type", "=", prefix)], limit=1)
        return last.user_id or self.env.ref("base.user_admin")

    def _document_alert(self, prefix, label, days_left, expiry, settings, expired=False):
        self.ensure_one()
        user = self._document_responsible_user(prefix)
        upcoming, expired_summary = self._document_alert_summaries(label)
        if expired:
            summary = expired_summary
            note = f"انتهت صلاحية {label} للموظف {self.name} منذ {abs(days_left)} يوم. يرجى التجديد فوراً."
            deadline = fields.Date.today()
        else:
            summary = upcoming
            note = f"ستنتهي صلاحية {label} للموظف {self.name} خلال {days_left} يوم بتاريخ {expiry}."
            deadline = fields.Date.today() + timedelta(days=min(days_left, 3))

        if settings.get("notify_activity", True):
            exists = self.env["mail.activity"].sudo().search_count([
                ("res_model", "=", "hr.employee"),
                ("res_id", "=", self.id),
                ("summary", "=", summary),
            ], limit=1)
            if not exists:
                activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
                self.activity_schedule(
                    act_type_xmlid="mail.mail_activity_data_todo" if activity_type else "",
                    summary=summary,
                    note=note,
                    date_deadline=deadline,
                    user_id=user.id,
                )
        # e-mail only on the alert days (not every day after expiry)
        if settings.get("notify_email") and not expired and user.partner_id.email:
            template = self.env.ref(
                "hr_employee_document_tracking.email_template_employee_document_alert",
                raise_if_not_found=False)
            if template:
                template.with_context(
                    doc_label=label, days_left=days_left, expiry_date=expiry,
                    responsible_partner_id=user.partner_id.id, responsible_name=user.name,
                ).send_mail(self.id, force_send=True)

    def _close_document_alerts(self, prefix):
        label = dict(DOC_TYPES)[prefix]
        self.env["mail.activity"].sudo().search([
            ("res_model", "=", "hr.employee"),
            ("res_id", "in", self.ids),
            ("summary", "in", list(self._document_alert_summaries(label))),
        ]).action_done()

    def _compute_document_history_count(self):
        data = self.env["hr.employee.document.history"]._read_group(
            [("employee_id", "in", self.ids)], ["employee_id"], ["__count"]
        )
        counts = {employee.id: count for employee, count in data}
        for emp in self:
            emp.document_history_count = counts.get(emp.id, 0)

    def action_open_document_renewal(self):
        self.ensure_one()
        doc_type = self.env.context.get("doc_type")
        return {
            "type": "ir.actions.act_window",
            "name": _("Renewal"),
            "res_model": "hr.employee.document.renewal",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_employee_id": self.id,
                "default_doc_type": doc_type,
            },
        }

    def action_open_document_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Renewal History"),
            "res_model": "hr.employee.document.history",
            "view_mode": "list,form",
            "views": [
                (self.env.ref("hr_employee_document_tracking.view_hr_employee_document_history_all_list").id, "list"),
                (False, "form"),
            ],
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id, "create": False},
        }
