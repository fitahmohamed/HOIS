# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class TenderDeductionType(models.Model):
    _name = 'tender.deduction.type'
    _description = 'Deduction / Allowance Type'
    _rec_name = 'name'

    name = fields.Char(string=_('Name'), required=True)
    type = fields.Selection([
        ('deduction', 'Deduction'),
        ('allowance', 'Allowance'),
    ], string=_('Type'), default='deduction', required=True)
    account_id = fields.Many2one('account.account', string=_('Account'))
    percentage = fields.Float(string=_('Percentage (%)'), help='Percentage to deduct/allow from contract total')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string=_('Company'))
