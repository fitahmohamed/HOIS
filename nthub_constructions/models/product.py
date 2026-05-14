# -*- coding: utf-8 -*-
from odoo import models, fields, api,_


class Product(models.Model):
    """
       Extends the 'product.template' model in Odoo to add custom boolean fields
       representing different categories related to a product.
    """
    _inherit = 'product.template'

    expenses = fields.Boolean(string=_("Expenses"))
    material = fields.Boolean(string=_("Material"))
    labour = fields.Boolean(string=_("Labour"))
    equipment = fields.Boolean(string=_("Equipment"))
    indirect_cost = fields.Boolean(string=_("Indirect Cost"))
    subcontractor = fields.Boolean(string=_("Subcontractor"))
    top_sheet = fields.Boolean(string=_("Top sheet"))


    @api.onchange('material')
    def _compute_detailed_type(self):
        """
           This method is an Odoo API onchange method that automatically computes the value of the 'type' field
           based on the value of the 'material' field.
           """
        for product in self:
            if product.material:
                product.type = 'consu'
            else:
                product.type = 'service'

    @api.onchange('expenses', 'labour', 'indirect_cost', 'subcontractor', 'top_sheet')
    def _compute_purchase_ok(self):
        """
            This method is an Odoo API onchange method that automatically computes the value of the 'purchase_ok' field
            based on the values of related cost fields (expenses, labour, indirect_cost, subcontractor, top_sheet).
            """
        for product in self:
            if any([product.expenses, product.labour, product.indirect_cost, product.subcontractor, product.top_sheet]):
                product.purchase_ok = False
            else:
                product.purchase_ok = True

