# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DownPaymentInvoiceWizard(models.TransientModel):
    _name = 'down.payment.invoice.wizard'
    _description = 'Down Payment Invoice Wizard'

    contract_id = fields.Many2one('owner.contract', string=_('Contract'), required=True)
    amount = fields.Float(string=_('Amount'), required=True)
    max_amount = fields.Float(string=_('Maximum Amount'))
    remaining_after = fields.Float(
        string=_('Remaining After Invoice'),
        compute='_compute_remaining_after')
    is_vendor = fields.Boolean(string=_('Vendor Invoice'))

    @api.depends('amount', 'max_amount')
    def _compute_remaining_after(self):
        for rec in self:
            rec.remaining_after = rec.max_amount - rec.amount

    def action_create_invoice(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('Amount must be greater than zero.'))
        if self.amount > self.max_amount + 0.01:
            raise UserError(
                _('Amount (%.2f) exceeds remaining (%.2f).')
                % (self.amount, self.max_amount))
        move_type = 'in_invoice' if self.is_vendor else 'out_invoice'
        invoice = self.contract_id._create_down_payment_invoice(
            self.amount, move_type=move_type)
        return {
            'name': _('Down Payment Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }
