# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import AccessError


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
    max_purchase_price = fields.Float(string=_("Max Purchase Price"))
    last_purchase_price = fields.Float(
        string=_("Last Purchase Price"),
        compute='_compute_last_purchase_price',
    )


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

    def _check_max_purchase_price_access(self, vals):
        if (
                'max_purchase_price' in vals
                and not self.env.user.has_group('nthub_constructions.construction_group_max_purchase_price')
        ):
            raise AccessError(_("You are not allowed to edit Max Purchase Price."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_max_purchase_price_access(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_max_purchase_price_access(vals)
        return super().write(vals)

    def _compute_last_purchase_price(self):
        PurchaseLine = self.env['purchase.order.line']
        for product in self:
            product.last_purchase_price = 0.0
            previous_line = PurchaseLine.search([
                ('product_id', 'in', product.product_variant_ids.ids),
                ('state', '=', 'purchase'),
                ('display_type', '=', False),
            ], order='date_approve desc, date_order desc, id desc', limit=1)
            if previous_line:
                product.last_purchase_price = previous_line.price_unit
