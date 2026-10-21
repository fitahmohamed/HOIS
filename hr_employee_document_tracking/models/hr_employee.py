from odoo import _, api, fields, models

from .document_common import LICENSE_TYPES, STATUS_SELECTION, compute_days

HR = "hr.group_hr_user"


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # ------------------------------------------------------------------ Passport
    passport_number = fields.Char(string="Passport Number", groups=HR, tracking=True)
    passport_country_id = fields.Many2one("res.country", string="Passport Issue Country", groups=HR)
    passport_file = fields.Binary(string="Passport File", attachment=True, groups=HR)
    passport_file_name = fields.Char(groups=HR)
    passport_note = fields.Text(string="Passport Note", groups=HR)
    passport_status = fields.Selection(STATUS_SELECTION, string="Passport Status", groups=HR)
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
    iqama_status = fields.Selection(STATUS_SELECTION, string="Iqama Status", groups=HR)
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
    license_status = fields.Selection(STATUS_SELECTION, string="License Status", groups=HR)
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
    driver_card_status = fields.Selection(STATUS_SELECTION, string="Driver Card Status", groups=HR)
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
    medical_status = fields.Selection(STATUS_SELECTION, string="Medical Insurance Status", groups=HR)
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
            for prefix in ("passport", "iqama", "license", "driver_card", "medical"):
                emp[f"{prefix}_remaining_days"] = compute_days(
                    emp[f"{prefix}_issue_date"], emp[f"{prefix}_expiry_date"]
                )

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
