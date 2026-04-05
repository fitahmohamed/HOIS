# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
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

