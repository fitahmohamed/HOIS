from odoo import api, fields, models

DOC_TYPES = [
    ("registration", "Vehicle Registration"),
    ("insurance", "Insurance Register"),
    ("mvpi", "MVPI"),
    ("authorization", "Vehicle Authorization"),
    ("operation_card", "Operation Card"),
]
PREFIXES = tuple(key for key, _label in DOC_TYPES)

# Same statuses as the "renewal_tracker" module, computed automatically
STATUS_SELECTION = [
    ("expired", "منتهي"),
    ("critical", "عاجل جداً"),
    ("warning", "قريب"),
    ("ok", "سليم"),
]

INSURANCE_TYPES = [
    ("comprehensive", "Comprehensive"),
    ("third_party", "Third Party"),
]

_COMMON = ["file", "file_name", "note", "issue_date", "expiry_date"]

# generic field (on wizard / history)  ->  field on fleet.vehicle, per document type
DOC_FIELD_MAP = {
    "registration": dict(
        {"number": "registration_number"},
        **{f: "registration_%s" % f for f in _COMMON},
    ),
    "insurance": dict(
        {
            "company": "insurance_company",
            "insurance_type": "insurance_type",
            "number": "insurance_policy_number",
            "amount": "insurance_amount",
        },
        **{f: "insurance_%s" % f for f in _COMMON},
    ),
    "mvpi": dict(
        {"number": "mvpi_number"},
        **{f: "mvpi_%s" % f for f in _COMMON},
    ),
    "authorization": dict(
        {"number": "authorization_number", "driver_id": "authorization_driver_id"},
        **{f: "authorization_%s" % f for f in _COMMON},
    ),
    "operation_card": dict(
        {"number": "operation_card_number"},
        **{f: "operation_card_%s" % f for f in _COMMON},
    ),
}


def days_left(expiry_date, today=None):
    """Remaining days = expiry date - today."""
    if not expiry_date:
        return 0
    return (expiry_date - (today or fields.Date.today())).days


def get_status(expiry_date, settings, today=None):
    """Status from the days left until expiry, using renewal_tracker settings."""
    if not expiry_date:
        return False
    left = days_left(expiry_date, today)
    if left < 0:
        return "expired"
    if left <= settings.get("critical_days", 7):
        return "critical"
    if left <= settings.get("warning_days", 30):
        return "warning"
    return "ok"


class FleetVehicleDocumentMixin(models.AbstractModel):
    """Generic document fields shared by the renewal wizard and the history lines."""

    _name = "fleet.vehicle.document.mixin"
    _description = "Vehicle Document Fields"

    doc_type = fields.Selection(DOC_TYPES, string="Document Type", required=True)
    number = fields.Char(string="Number")
    company = fields.Char(string="Insurance Company")
    insurance_type = fields.Selection(INSURANCE_TYPES, string="Insurance Type")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(string="Amount", currency_field="currency_id")
    driver_id = fields.Many2one("res.partner", string="Authorized Driver")
    file = fields.Binary(string="Upload File", attachment=True)
    file_name = fields.Char(string="File Name")
    note = fields.Text()
    issue_date = fields.Date()
    expiry_date = fields.Date()
    remaining_days = fields.Integer(compute="_compute_remaining_days")

    @api.depends("expiry_date")
    def _compute_remaining_days(self):
        today = fields.Date.today()
        for rec in self:
            rec.remaining_days = days_left(rec.expiry_date, today)
