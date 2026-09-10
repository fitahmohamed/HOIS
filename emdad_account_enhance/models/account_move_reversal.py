# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    reversal_datetime = fields.Datetime(
        string='Reversal Date & Time',
        readonly=True,
        default=fields.Datetime.now,
    )