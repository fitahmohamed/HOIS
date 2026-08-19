# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class OwnerContractCompletionInherit(models.Model):
    _inherit = 'owner.contract'

    def _build_prev_done_for_contract(self):
        """Return {item_id: total_qty_done} from confirmed completion requests."""
        confirmed = self.env['project.completion.request'].search([
            ('contract_id', '=', self.id),
            ('state', 'in', ('confirm', 'invoiced')),
        ])
        prev_done = {}
        for req in confirmed:
            for line in req.line_ids:
                if line.quantity > 0 and line.state in ('accept', 'partially'):
                    prev_done[line.item_id.id] = (
                        prev_done.get(line.item_id.id, 0) + line.quantity)
        return prev_done

    def _create_completion_request(self, date=False, n=0):
        """Override: add contract_qty, prev_completed_qty, analytic_distribution."""
        prev_done = self._build_prev_done_for_contract()
        completion_request_lines = []
        for cl in self.owner_contract_line_ids:
            if not cl.item_id:
                continue
            prev_qty = prev_done.get(cl.item_id.id, 0)
            quantity, difference = self._calculate_quantity_and_difference(cl, n)
            completion_request_lines.append((0, 0, {
                'item_id': cl.item_id.id,
                'description': cl.description,
                'uom_id': cl.uom_id.id if cl.uom_id else False,
                'price_unit': cl.price_unit,
                'percentage': 0,
                'quantity': quantity + difference,
                'contract_qty': cl.quantity,
                'prev_completed_qty': prev_qty,
                'analytic_distribution': cl.analytic_distribution or {},
            }))
        vals = {
            'project_id': self.project_id.id,
            'contract_id': self.id,
            'date': date if self.generation_method == 'duration' else fields.Date.today(),
            'reference': self.name,
            'type': 'initial',
            'state': 'draft',
            'line_ids': completion_request_lines,
        }
        self.env['project.completion.request'].create(vals)
