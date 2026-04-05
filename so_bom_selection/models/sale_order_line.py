# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    bom_id = fields.Many2one('mrp.bom', string='Bill of Material',
                             help="Bill of materials for the product")
    product_template_id = fields.Many2one(related="product_id.product_tmpl_id",
                                          string="Template Id of Selected"
                                                 " Product",
                                          help="Template id of the "
                                               "selected product")

    def _action_launch_stock_rule(self, **kwargs):
        result = super(SaleOrderLine, self)._action_launch_stock_rule(**kwargs)
        for rec in self:
            if rec.bom_id:
                mo = self.env['mrp.production'].search(
                    [('sale_line_id', '=', rec.id)])
                if mo:
                    move = self.env['stock.move'].search(
                        [('sale_line_id', '=', rec.id)])
                    if not move.created_production_id:
                        move.created_production_id = mo.id
        return result
