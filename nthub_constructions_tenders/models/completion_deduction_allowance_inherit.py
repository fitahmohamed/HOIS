# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class CompletionDeductionAllowanceInherit(models.Model):
    _inherit = 'contract.completion.deduction.allowance'

    deduction_type_id = fields.Many2one(
        'tender.deduction.type', string=_('Type'),
        domain="[('type', '=', main_type)]")
    account_id = fields.Many2one('account.account', string=_('Account'))

    @api.onchange('deduction_type_id')
    def _onchange_deduction_type_id(self):
        for rec in self:
            if rec.deduction_type_id:
                rec.name = rec.deduction_type_id.name
                rec.account_id = rec.deduction_type_id.account_id.id
                if rec.deduction_type_id.percentage:
                    rec.percentage = rec.deduction_type_id.percentage / 100.0
                    rec.calculation_type = 'percentage'
