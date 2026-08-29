# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProjectOverheadType(models.Model):
    """Master data for overhead cost items — pick from here when filling
    project or offer overhead lines."""
    _name = 'project.overhead.type'
    _description = 'Overhead Type'
    _rec_name = 'name'
    _order = 'category, name'

    name = fields.Char(string='Name', required=True, translate=True)

    category = fields.Selection([
        ('labour',      'Labour'),
        ('engineering', 'Engineering & Supervision'),
        ('expenses',    'Expenses'),
        ('equipment',   'Equipment'),
        ('other',       'Other'),
    ], string='Category', default='other', required=True)

    account_id = fields.Many2one(
        'account.account', string='Account',
        help='Accounting account linked to this overhead type.')

    uom_name = fields.Char(string='Unit', help='e.g. Hour / Day / Month / Lump Sum')
    unit_price = fields.Float(string='Default Unit Cost', default=0.0)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)

    notes = fields.Text(string='Notes')
