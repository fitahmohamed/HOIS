from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LaborRulesConfig(models.Model):
    _name = "labor.rules.config"
    _description = "Labor Rules Configuration"
    _order = "sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    is_default = fields.Boolean(
        string="Default for Company",
        help="If enabled, this configuration is auto-selected for labor lines in the same company.",
    )

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    iqama_fee = fields.Monetary(currency_field="currency_id")
    work_permit_fee = fields.Monetary(currency_field="currency_id")
    visa_fee = fields.Monetary(currency_field="currency_id")
    exit_reentry_visa_fee = fields.Monetary(currency_field="currency_id")
    medical_insurance_fee = fields.Monetary(currency_field="currency_id")

    @api.constrains("name", "company_id")
    def _check_name_unique_per_company(self):
        for rec in self:
            if not rec.name or not rec.company_id:
                continue
            duplicate_count = self.search_count(
                [
                    ("id", "!=", rec.id),
                    ("company_id", "=", rec.company_id.id),
                    ("name", "=", rec.name),
                ]
            )
            if duplicate_count:
                raise ValidationError("Configuration name must be unique per company.")

    @api.constrains("is_default", "company_id", "active")
    def _check_single_default_per_company(self):
        for rec in self.filtered(lambda r: r.is_default and r.active and r.company_id):
            duplicate_count = self.search_count(
                [
                    ("id", "!=", rec.id),
                    ("company_id", "=", rec.company_id.id),
                    ("is_default", "=", True),
                    ("active", "=", True),
                ]
            )
            if duplicate_count:
                raise ValidationError("Only one active default configuration is allowed per company.")

    @classmethod
    def _default_for_company(cls, env, company):
        return env["labor.rules.config"].search(
            [
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("is_default", "=", True),
            ],
            order="sequence, id",
            limit=1,
        )
