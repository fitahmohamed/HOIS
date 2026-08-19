# -*- coding: utf-8 -*-
from datetime import date
from odoo import models, fields, api, _


class Project(models.Model):
    _inherit = 'project.project'

    warehouse_id = fields.Many2one('stock.warehouse', string=_('Warehouse'))
