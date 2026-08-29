# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    down_payment_account_id = fields.Many2one(
        'account.account',
        string='Down Payment Account',
        config_parameter='nthub_tenders.down_payment_account_id',
        help='Default account used when creating down payment invoices from contracts.')
