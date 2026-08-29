# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProjectOverheadLine(models.Model):
    _name = 'project.overhead.line'
    _description = 'Project Overhead Line'
    _rec_name = 'name'

    project_id = fields.Many2one('project.project', string='Project',
                                  ondelete='cascade', required=True, index=True)

    type_id = fields.Many2one(
        'project.overhead.type', string='Overhead Type',
        help='Select a predefined overhead type to auto-fill values.')

    name = fields.Char(string='Description', required=True)

    category = fields.Selection([
        ('labour',      'Labour'),
        ('engineering', 'Engineering & Supervision'),
        ('expenses',    'Expenses'),
        ('equipment',   'Equipment'),
        ('other',       'Other'),
    ], string='Category', default='other', required=True)

    uom_name = fields.Char(string='Unit', help='e.g. Hour / Day / Month / Lump Sum')
    qty = fields.Float(string='Quantity', default=1.0, digits=(16, 4))
    unit_price = fields.Float(string='Unit Cost', default=0.0)
    duration_months = fields.Float(
        related='project_id.project_duration_months',
        string='Months',
        store=False,
        readonly=True,
    )
    amount = fields.Float(string='Amount', compute='_compute_amount', store=True)

    @api.depends('qty', 'unit_price', 'project_id.project_duration_months')
    def _compute_amount(self):
        for rec in self:
            months = rec.project_id.project_duration_months if rec.project_id else 1.0
            rec.amount = rec.qty * (months or 1.0) * rec.unit_price

    @api.onchange('type_id')
    def _onchange_type_id(self):
        for rec in self:
            if rec.type_id:
                rec.name = rec.type_id.name
                rec.category = rec.type_id.category
                rec.uom_name = rec.type_id.uom_name or rec.uom_name
                rec.unit_price = rec.type_id.unit_price

    def _trigger_offer_recompute(self):
        projects = self.mapped('project_id')
        if projects:
            projects._recompute_offers_direct_costs()

    def create(self, vals_list):
        records = super().create(vals_list)
        records._trigger_offer_recompute()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._trigger_offer_recompute()
        return res

    def unlink(self):
        projects = self.mapped('project_id')
        res = super().unlink()
        projects._recompute_offers_direct_costs()
        return res
