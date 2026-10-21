from odoo import fields, models


class HrVisaProfession(models.Model):
    _name = "hr.visa.profession"
    _description = "Visa Profession"
    _order = "sequence, name"

    name = fields.Char(string="Visa Profession", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint("UNIQUE(name)", "This visa profession already exists.")


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    staff_type = fields.Selection(
        [
            ("operator", "Operator"),
            ("driver", "Driver"),
            ("office_staff", "Office Staff"),
            ("other", "Other"),
        ],
        string="Employee Type",
        groups="hr.group_hr_user",
        tracking=True,
    )
    visa_profession_id = fields.Many2one(
        "hr.visa.profession",
        string="Visa Profession",
        groups="hr.group_hr_user",
        tracking=True,
    )
