# -*- coding: utf-8 -*-
from odoo import models, fields, _


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    contract_down_payment_id = fields.Many2one(
        'owner.contract', string=_('Contract'), index=True, ondelete='set null')

    deduction_return_contract_id = fields.Many2one(
        'owner.contract', string=_('Contract (Deduction Return)'),
        index=True, ondelete='set null')
