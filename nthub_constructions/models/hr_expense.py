# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class CustomExpense(models.Model):
    _inherit = 'hr.expense'

    delivery_request_id = fields.Many2one('subcontractor.delivery.request',string="Delivery Request")
    customer_id = fields.Many2one('res.partner', related='delivery_request_id.contract_id.partner_id')
