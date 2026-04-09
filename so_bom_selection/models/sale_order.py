# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        # --- Freeze BOM unit cost on every line before the state changes ---
        # Writing bom_unit_cost here ensures the snapshot is taken from the
        # current BOM state at the exact moment of confirmation.
        # After this point the field is a plain stored Float with no compute
        # dependency on BOM data, so future BOM edits cannot touch it.
        for line in self.order_line:
            if line.bom_id:
                line.bom_unit_cost = line._calc_bom_unit_cost()

        # --- Existing BOM sequence priority logic ---
        for rec in self.order_line:
            if rec.bom_id and rec.bom_id in rec.product_template_id.bom_ids:
                original_sequences = {bom.id: bom.sequence for bom in rec.product_template_id.bom_ids}
                rec.bom_id.sequence = 0
                other_boms = rec.product_template_id.bom_ids - rec.bom_id
                sequence_counter = 1
                for bom in other_boms.sorted('sequence'):
                    bom.sequence = sequence_counter
                    sequence_counter += 1

        result = super().action_confirm()

        # --- Restore BOM sequences and sync MO quantities ---
        for rec in self.order_line:
            if rec.bom_id and rec.bom_id in rec.product_template_id.bom_ids:
                for bom in rec.product_template_id.bom_ids:
                    if bom.id in original_sequences:
                        bom.sequence = original_sequences[bom.id]
            manufacturing_order = self.env["mrp.production"].search(
                [('origin', '=', self.name),
                 ('state', '=', 'confirmed')])
            if manufacturing_order:
                for mo in manufacturing_order:
                    print(mo.product_qty)
                    mo.update({'qty_to_produce': mo.product_qty})

        return result

    def action_refresh_bom_costs(self):
        """Refresh bom_unit_cost for all lines from current BOM component prices.
        Only works on draft/sent orders. Also recalculates price_unit when a
        margin percentage is set on the line."""
        for line in self.order_line:
            if line.bom_id:
                line.bom_unit_cost = line._calc_bom_unit_cost()
                if line.margin_percentage:
                    divisor = 1.0 - (line.margin_percentage / 100.0)
                    if divisor > 0:
                        line.price_unit = line.bom_unit_cost / divisor

    def write(self, values):
        res = super().write(values)
        for order_line in self.order_line:
            if order_line.product_uom_qty:
                manufacturing_order = self.env["mrp.production"].search(
                    [('origin', '=', self.name),
                     ('state', '=', 'confirmed')])
                if manufacturing_order:
                    for mo in manufacturing_order:
                        mo.write({'qty_to_produce': mo.product_qty})
        return res
