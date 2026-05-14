# -*- coding: utf-8 -*-

from odoo import models, fields, api

class MaterialPurchaseRequisitionLine(models.Model):
    _name = "material.purchase.requisition.line"
    _description = 'Material Purchase Requisition Lines'

    
    requisition_id = fields.Many2one(
        'material.purchase.requisition',
        string='Requisitions', 
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )
#     layout_category_id = fields.Many2one(
#         'sale.layout_category',
#         string='Section',
#     )
    description = fields.Char(
        string='Description',
        required=True,
    )
    qty = fields.Float(
        string='Quantity',
        default=1,
        required=True,
    )

    available_qty = fields.Float(
        string='Available Quantity',
        compute = '_compute_available_qty',
    )

    uom = fields.Many2one(
        'uom.uom',#product.uom in odoo11
        string='Unit of Measure',
        required=True,
    )
    partner_id = fields.Many2many(
        'res.partner',
        string='Vendors',
    )
    requisition_type = fields.Selection(
        selection=[
                    ('internal','Internal Picking'),
                    ('purchase','Purchase Order'),
        ],
        string='Requisition Action',
        default='internal',
        required=True,
    )
    @api.onchange('product_id')
    def onchange_product_id(self):
        """
           Onchange method triggered when the 'product_id' field is changed.
           Updates the 'description' field with the name of the selected product
           and sets the 'uom' field to the unit of measure ID of the selected product.
"""
        for rec in self:
            rec.description = rec.product_id.name
            rec.uom = rec.product_id.uom_id.id

    @api.depends('product_id','requisition_id.location_id')
    def _compute_available_qty(self):
        """
            Compute method to update the 'available_qty' field based on the 'product_id'
            and the 'location_id' from the related requisition.
            If both 'product_id' and 'location_id' are set, it calculates the available quantity
            in the specified location for the given product. If only 'product_id' is set,
            it calculates the overall available quantity for the product across all internal locations.
            """
        for rec in self:
            if rec.product_id and rec.requisition_id.location_id:
                domain = [('product_id', '=', rec.product_id.id), ('location_id.usage', '=', 'internal'),
                          ('location_id', '=', self.requisition_id.location_id.id)]
                stock_quant = self.env['stock.quant'].sudo().search(domain)
                if stock_quant:
                    rec.available_qty = sum(stock_quant.mapped('quantity'))
                else:
                    rec.available_qty = 0
            elif rec.product_id:
                domain = [('product_id', '=', rec.product_id.id), ('location_id.usage', '=', 'internal')]
                stock_quant = self.env['stock.quant'].sudo().search(domain)
                qty = stock_quant.mapped('quantity')
                if stock_quant:
                    rec.available_qty = sum(qty)
                else:
                    rec.available_qty = 0
            else:
                rec.available_qty = 0