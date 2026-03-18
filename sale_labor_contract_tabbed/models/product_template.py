from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_is_labor_outsourcing = fields.Boolean(
        string="Is Labor Outsourcing",
        help="Enable labor outsourcing calculations when this product is used on sales order lines.",
    )
