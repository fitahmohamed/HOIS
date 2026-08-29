# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SubcontractorDeliveryRequestLineInherit(models.Model):
    _inherit = 'subcontractor.delivery.request.line'

    # Contract info fields
    contract_qty = fields.Float(string=_('Contract Qty'), readonly=True)
    prev_completed_qty = fields.Float(string=_('Prev. Done'), readonly=True)

    remaining_contract_qty = fields.Float(
        string=_('Remaining'),
        compute='_compute_contract_progress')

    overall_completion_pct = fields.Float(
        string=_('Overall %'),
        compute='_compute_contract_progress')

    # % of the base contract quantity to complete in this period
    completion_percentage = fields.Float(
        string=_('Percentage'),
        help='Percentage of the base contract quantity (Contract Qty) to '
             'complete in this period (0 to 1)')

    @api.depends('contract_qty', 'prev_completed_qty', 'quantity')
    def _compute_contract_progress(self):
        for rec in self:
            rec.remaining_contract_qty = rec.contract_qty - rec.prev_completed_qty
            if rec.contract_qty > 0:
                rec.overall_completion_pct = (
                    rec.prev_completed_qty + rec.quantity) / rec.contract_qty
            else:
                rec.overall_completion_pct = 0.0

    @api.onchange('quantity')
    def _onchange_quantity_update_amount(self):
        """When qty entered: compute amount and update completion_percentage
        based on the base contract quantity (contract_qty), not the
        remaining quantity."""
        for rec in self:
            rec.amount = rec.quantity * rec.price_unit
            if rec.contract_qty > 0:
                rec.completion_percentage = rec.quantity / rec.contract_qty
            else:
                rec.completion_percentage = 1.0 if rec.quantity > 0 else 0.0
            if rec.quantity > 0:
                rec.state = 'accept'
            else:
                rec.state = ' '

    @api.onchange('completion_percentage')
    def _onchange_completion_percentage(self):
        """When % entered: compute qty and amount based on the base
        contract quantity (contract_qty), not the remaining quantity."""
        for rec in self:
            if rec.contract_qty > 0:
                rec.quantity = rec.contract_qty * rec.completion_percentage
                rec.amount = rec.quantity * rec.price_unit
                if rec.completion_percentage >= 1.0:
                    rec.state = 'accept'
                elif rec.completion_percentage > 0:
                    rec.state = 'partially'
                else:
                    rec.state = ' '
