# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class Stages(models.Model):
    _name = 'constructions.stages'
    _description = 'nthub_constructions.stages'

    name = fields.Char(string=_("Name"))
    ar_name = fields.Char(string=_("Arabic Name"))



