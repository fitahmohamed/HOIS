# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    source = fields.Char(string='Source of Order',
                         help='Sale Order from which this Manufacturing '
                              'Order created.')
    sale_line_id = fields.Many2one('sale.order.line', string='Sale Line',
                                   help="Corresponding sale order line id")

    qty_to_produce = fields.Float(string='Quantity to Produce',
                                  help='The number of products to be produced.')
