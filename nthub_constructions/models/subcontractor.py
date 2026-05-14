# -*- coding: utf-8 -*-
from odoo import models, fields, api,_


class SubContractor(models.Model):
    _inherit = 'res.partner'

    is_subcontractor = fields.Boolean(string=_("Subcontractor"))

