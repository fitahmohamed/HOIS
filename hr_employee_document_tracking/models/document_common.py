from odoo import api, fields, models

DOC_TYPES = [
    ("passport", "Passport"),
    ("iqama", "Iqama"),
    ("license", "Driving License"),
    ("driver_card", "Driver Card"),
    ("medical", "Medical Insurance"),
]

STATUS_SELECTION = [
    ("valid", "Valid"),
    ("under_renewal", "Under Renewal"),
    ("expired", "Expired"),
    ("cancelled", "Cancelled"),
]

LICENSE_TYPES = [
    ("heavy", "Heavy Driving"),
    ("light", "Light Driving"),
    ("equipment", "Equipment Operation"),
    ("card", "Card"),
]

_COMMON = ["file", "file_name", "note", "status", "issue_date", "expiry_date"]

# generic field (on wizard / history)  ->  field on hr.employee, per document type
DOC_FIELD_MAP = {
    "passport": dict(
        {"number": "passport_number", "country_id": "passport_country_id"},
        **{f: "passport_%s" % f for f in _COMMON},
    ),
    "iqama": dict(
        {
            "number": "iqama_number",
            "profession": "iqama_profession",
            "sponsor": "iqama_sponsor",
            "country_id": "iqama_country_id",
        },
        **{f: "iqama_%s" % f for f in _COMMON},
    ),
    "license": dict(
        {
            "number": "license_number",
            "license_type": "license_type",
            "authority": "license_authority",
        },
        **{f: "license_%s" % f for f in _COMMON},
    ),
    "driver_card": dict(
        {"number": "driver_card_number"},
        **{f: "driver_card_%s" % f for f in _COMMON},
    ),
    "medical": dict(
        {
            "number": "medical_policy_number",
            "company": "medical_company",
            "membership_number": "medical_membership_number",
            "insurance_type": "medical_type",
        },
        **{f: "medical_%s" % f for f in _COMMON},
    ),
}


def compute_days(issue_date, expiry_date):
    if issue_date and expiry_date:
        return (expiry_date - issue_date).days
    return 0


class HrEmployeeDocumentMixin(models.AbstractModel):
    """Generic document fields shared by the renewal wizard and the history lines."""

    _name = "hr.employee.document.mixin"
    _description = "Employee Document Fields"

    doc_type = fields.Selection(DOC_TYPES, string="Document Type", required=True)
    number = fields.Char(string="Number")
    country_id = fields.Many2one("res.country", string="Issue Country")
    profession = fields.Char()
    sponsor = fields.Char()
    license_type = fields.Selection(LICENSE_TYPES, string="License Type")
    authority = fields.Char()
    company = fields.Char(string="Insurance Company")
    membership_number = fields.Char()
    insurance_type = fields.Char(string="Type")
    file = fields.Binary(string="Upload File", attachment=True)
    file_name = fields.Char(string="File Name")
    note = fields.Text()
    status = fields.Selection(STATUS_SELECTION, default="valid")
    issue_date = fields.Date()
    expiry_date = fields.Date()
    remaining_days = fields.Integer(compute="_compute_remaining_days", store=True)

    @api.depends("issue_date", "expiry_date")
    def _compute_remaining_days(self):
        for rec in self:
            rec.remaining_days = compute_days(rec.issue_date, rec.expiry_date)
