# -*- coding: utf-8 -*-
'''
model Project Unit Type
'''
from odoo import models, fields, api, _

class ProjectUnitType(models.Model):
    _name = 'project.unit.type'
    _description = 'Project Unit Type'
    _rec_name = "name"

    name = fields.Char(string=_("Name"))
    description = fields.Text(string=_("Description"))

