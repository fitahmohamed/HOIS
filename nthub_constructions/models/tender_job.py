# -*- coding: utf-8 -*-
'''
model tender job
'''
from odoo import models, fields, api, _

class TenderJob(models.Model):
    _name = 'tender.job'
    _description = 'tender'
    _rec_name = "name"

    name = fields.Char(string=_("Name"))
    code = fields.Char(string=_("Code"))

