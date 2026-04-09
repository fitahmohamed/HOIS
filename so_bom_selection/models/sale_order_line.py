# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    bom_id = fields.Many2one('mrp.bom', string='Bill of Material',
                             help="Bill of materials for the product")
    product_template_id = fields.Many2one(related="product_id.product_tmpl_id",
                                          string="Template Id of Selected Product",
                                          help="Template id of the selected product")

    # Plain stored field — written by onchange and frozen at confirmation.
    # Has NO compute dependency on BOM lines, so BOM changes after
    # confirmation have zero effect on this value.
    bom_unit_cost = fields.Float(
        string='BOM Unit Cost',
        store=True,
        digits='Product Price',
        help="Cost per finished unit based on BOM components at the time of selection. "
             "Frozen permanently when the sale order is confirmed.",
    )

    # Computed only from bom_unit_cost × qty — no BOM line dependency.
    # Responds correctly to quantity changes but is immune to BOM edits.
    bom_total_cost = fields.Float(
        string='BOM Total Cost',
        compute='_compute_bom_total_cost',
        store=True,
        digits='Product Price',
        help="Total BOM cost for this line (BOM unit cost × ordered quantity).",
    )

    margin_percentage = fields.Float(
        string='Margin (%)',
        digits=(5, 2),
        help="Gross margin percentage. Unit price is recalculated as: "
             "BOM unit cost ÷ (1 − margin% / 100)",
    )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _calc_bom_unit_cost(self):
        """Return the cost per finished unit for the selected BOM.
        Reads BOM lines live — only called from onchanges and at confirmation."""
        self.ensure_one()
        if self.bom_id and self.bom_id.bom_line_ids:
            component_cost = sum(
                bl.product_id.standard_price * bl.product_qty
                for bl in self.bom_id.bom_line_ids
            )
            return component_cost / (self.bom_id.product_qty or 1)
        return 0.0

    # -------------------------------------------------------------------------
    # Computed fields
    # -------------------------------------------------------------------------

    @api.depends('bom_unit_cost', 'product_uom_qty')
    def _compute_bom_total_cost(self):
        for line in self:
            line.bom_total_cost = line.bom_unit_cost * line.product_uom_qty

    # -------------------------------------------------------------------------
    # Onchanges
    # -------------------------------------------------------------------------

    @api.onchange('bom_id')
    def _onchange_bom_id_cost(self):
        """When BOM is selected/changed: refresh unit cost snapshot and
        recalculate unit price if a margin is already set."""
        for line in self:
            line.bom_unit_cost = line._calc_bom_unit_cost()
            if line.margin_percentage:
                divisor = 1.0 - (line.margin_percentage / 100.0)
                if divisor > 0:
                    line.price_unit = line.bom_unit_cost / divisor

    @api.onchange('margin_percentage')
    def _onchange_margin_percentage(self):
        """When margin changes: recalculate unit price from the stored
        BOM unit cost (not from live BOM lines)."""
        for line in self:
            if not line.bom_unit_cost:
                continue
            divisor = 1.0 - (line.margin_percentage / 100.0)
            if divisor > 0:
                line.price_unit = line.bom_unit_cost / divisor

    # -------------------------------------------------------------------------
    # Stock rule override (unchanged)
    # -------------------------------------------------------------------------

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
