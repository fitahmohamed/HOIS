# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class CompletionRequestLineInherit(models.Model):
    _inherit = 'project.completion.request.line'

    # Read-only info from contract
    contract_qty = fields.Float(string=_('Contract Qty'), readonly=True)
    prev_completed_qty = fields.Float(string=_('Prev. Done'), readonly=True)

    remaining_contract_qty = fields.Float(
        string=_('Remaining'),
        compute='_compute_contract_progress')

    # Overall completion percentage = (prev_done + current_qty) / contract_qty
    overall_completion_pct = fields.Float(
        string=_('Overall %'),
        compute='_compute_contract_progress',
        help='Overall completion percentage from total contract quantity')

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

    def _ensure_contract_data(self):
        """لو بيانات العقد (كمية العقد / السعر) مش متسجلة على السطر —
        زي السطور القديمة أو اللي اتضافت يدوي — نجيبها من بند العقد.
        من غيرها إدخال النسبة كان بيدي صفر لأن contract_qty = 0."""
        for rec in self:
            if rec.contract_qty or not rec.item_id:
                continue
            contract = rec.completion_request_id.contract_id
            if not contract:
                continue
            cl = contract.owner_contract_line_ids.filtered(
                lambda l: l.item_id == rec.item_id)[:1]
            if cl:
                rec.contract_qty = cl.quantity
                if not rec.price_unit:
                    rec.price_unit = cl.price_unit

    @api.onchange('quantity')
    def _onchange_quantity_update_amount(self):
        """When qty entered: compute amount and update completion_percentage
        based on the base contract quantity (contract_qty), not the
        remaining quantity."""
        self._ensure_contract_data()
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
        self._ensure_contract_data()
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
            elif rec.completion_percentage:
                return {'warning': {
                    'title': _('Missing Contract Quantity'),
                    'message': _('البند "%s" مالوش كمية عقد مسجلة — '
                                 'اتأكد إن البند موجود في العقد أو أعد تحميل البنود.'
                                 ) % (rec.item_id.name or ''),
                }}

    @api.onchange('amount')
    def _onchange_amount(self):
        """Override للأصلية: كانت بتقسم على total_amount من غير حماية —
        لو الكمية لسه صفر كانت بتضرب ZeroDivisionError."""
        for rec in self:
            if rec.amount > 0 and rec.total_amount > 0:
                rec.percentage = rec.amount / rec.total_amount
                if rec.percentage >= 1:
                    rec.state = 'accept'
                else:
                    rec.state = 'partially'
            elif rec.amount <= 0:
                rec.percentage = 0
                rec.state = 'reject'
