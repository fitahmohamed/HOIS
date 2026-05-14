# -*- coding: utf-8 -*-
'''This model contains the project tender lines that used in the project tender'''
from odoo import models, fields, api, _


class ProjectTender(models.Model):
    _name = 'project.tender'
    _description = 'Project tender lines'
    _rec_name = 'item_id'

    project_id = fields.Many2one('project.project', string=_('Project'), help='project', ondelete='cascade', copy=False)
    item_id = fields.Many2one('tender.item', string=_('Item'), help='Item', copy=False, required=True)
    template_id = fields.Many2one('tender.job.cost', string=_("Template"), domain="[('state', '=', 'approve')]")
    description = fields.Char(string=_('Description'), help='Description', copy=False)
    reference = fields.Char(string=_('Reference'), help='Reference', copy=False)
    date = fields.Date(string=_('Date'), help='Date', required=True, default=fields.Date.today(), copy=False)
    qty = fields.Float(string=_('Planned Qty'), copy=False)
    qty_actual = fields.Float(string=_('Actual Qty'), copy=False)
    uom_id = fields.Many2one('uom.uom', string=_('Uom'))
    unit_price = fields.Float(string=_('Cost / Unit'), copy=False)
    total_cost = fields.Float(string=_('Cost Price Sub Total'), compute='_compute_total_cost', store=True)
    currency_id = fields.Many2one('res.currency', string=_('Currency'),
                                  related='project_id.currency_id', readonly=True)
    flag = fields.Selection(
        [('m', 'Material'), ('l', 'labour'), ('e', 'Expenses'), ('q', 'Equipment'), ('s', 'subcontractor')],
        string=_('Type'), required=True, )
    company_id = fields.Many2one(related='project_id.company_id', readonly=True)

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Update the price_unit field based on the selected template's jobcost_total."""
        if self.template_id:
            self.unit_price = self.template_id.jobcost_total

    @api.onchange('item_id')
    def _onchange_item_id(self):
        """Update the description and qty fields based on the selected item."""
        for rec in self:
            rec.description = rec.item_id.name
            rec.qty = 1.0
            rec.uom_id = rec.item_id.uom_id.id

    @api.depends('qty', 'unit_price', 'project_id')
    def _compute_total_cost(self):
        """Update the total_cost field based on the qty and unit_price fields."""
        for rec in self:
            rec.total_cost = rec.qty * rec.unit_price

