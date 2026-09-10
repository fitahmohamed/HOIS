# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    date = fields.Datetime(
        string='Reversal date',
        required=True,
        readonly=True,
        default=lambda self: fields.Datetime.now(),
    )