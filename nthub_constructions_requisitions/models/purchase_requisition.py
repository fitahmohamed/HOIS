# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date
from odoo.exceptions import  UserError

class MaterialPurchaseRequisition(models.Model):
    _inherit = 'material.purchase.requisition'

    
    project_id = fields.Many2one('project.project', string=_('Project'))
