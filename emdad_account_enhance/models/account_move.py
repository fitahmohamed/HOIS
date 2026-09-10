# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    vs_po_contract_ref = fields.Char(string='PO/Contract Reference')

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if not move.vs_po_contract_ref:
                # نجيب الـ sale order المرتبط بالفاتورة
                sale_order = move.invoice_line_ids.sale_line_ids.order_id[:1]
                if sale_order and sale_order.vs_po_contract_ref:
                    move.vs_po_contract_ref = sale_order.vs_po_contract_ref
        return moves
    from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    display_payment_status = fields.Char(
        compute='_compute_display_payment_status',
        string='Status'
    )

    @api.depends('state', 'payment_state')
    def _compute_display_payment_status(self):
        for move in self:
            if move.state == 'draft':
                move.display_payment_status = 'Draft'
            elif move.state == 'cancel':
                move.display_payment_status = 'Cancelled'
            elif move.payment_state == 'paid':
                move.display_payment_status = 'Paid'
            elif move.payment_state == 'partial':
                move.display_payment_status = 'Partial'
            elif move.payment_state == 'not_paid':
                move.display_payment_status = 'Not Paid'
            elif move.payment_state == 'in_payment':
                move.display_payment_status = 'In Payment'
            else:
                move.display_payment_status = move.state