# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContractDeductionAllowanceInherit(models.Model):
    _inherit = 'contract.deduction.allowance'

    deduction_type_id = fields.Many2one(
        'tender.deduction.type', string=_('Type'),
        domain="[('type', '=', main_type)]")
    account_id = fields.Many2one('account.account', string=_('Account'))

    @api.constrains('percentage')
    def check_percentage(self):
        for rec in self:
            if rec.calculation_type == 'percentage' and rec.percentage > 1:
                raise UserError(_('Percentage should be less than 100.'))

    @api.onchange('deduction_type_id')
    def _onchange_deduction_type_id(self):
        for rec in self:
            if rec.deduction_type_id:
                rec.name = rec.deduction_type_id.name
                rec.percentage = rec.deduction_type_id.percentage / 100.0
                rec.account_id = rec.deduction_type_id.account_id.id
                rec.calculation_type = 'percentage'
                if rec.contract_id and rec.contract_id.total_amount:
                    rec.amount = rec.contract_id.total_amount * rec.deduction_type_id.percentage / 100.0
