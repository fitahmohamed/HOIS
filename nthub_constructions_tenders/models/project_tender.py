# -*- coding: utf-8 -*-
'''This model contains the project tender lines that used in the project tender'''
from odoo import models, fields, api, _


class ProjectTender(models.Model):
    _name = 'project.tender'
    _description = 'Project tender lines'
    _rec_name = 'item_id'

    project_id = fields.Many2one('project.project', string=_('Project'), help='project', ondelete='cascade', copy=False)
    item_id = fields.Many2one('tender.item', string=_('Item'), help='Item', copy=False, required=True)
    item_name = fields.Char(related='item_id.name', string=_('Item Name'), readonly=True)
    item_code = fields.Char(related='item_id.code', string=_('Item Code'), readonly=True)
    # البريك داون المرتبط بالبند فقط (بكود البند واسمه) — مش كله في بعضه
    allowed_template_ids = fields.Many2many(
        'tender.job.cost', string=_('Allowed Templates'),
        compute='_compute_allowed_template_ids')
    template_id = fields.Many2one(
        'tender.job.cost', string=_('Template'),
        domain="[('id', 'in', allowed_template_ids)]")

    @api.depends('item_id', 'item_id.code', 'item_id.name', 'reference')
    def _compute_allowed_template_ids(self):
        """البريك داون اللي يخص البند ده فقط: نفس الكود أو نفس الاسم."""
        JobCost = self.env['tender.job.cost']
        for rec in self:
            legs = []
            code = rec.reference or rec.item_id.code
            if code:
                legs.append(('tender_item_code', '=', code))
            if rec.item_id.name:
                legs.append(('tender_item_name', '=', rec.item_id.name))
            if not legs:
                rec.allowed_template_ids = False
                continue
            domain = [('state', '!=', 'cancel')]
            if len(legs) == 2:
                domain += ['|'] + legs
            else:
                domain += legs
            rec.allowed_template_ids = JobCost.search(domain).ids
    description = fields.Char(string=_('Description'), help='Description', copy=False)
    reference = fields.Char(string=_('Reference'), help='Reference', copy=False)
    date = fields.Date(string=_('Date'), help='Date', required=True, default=fields.Date.today(), copy=False)
    qty = fields.Float(string=_('Planned Qty'), copy=False)
    qty_actual = fields.Float(string=_('Actual Qty'), copy=False)
    uom_id = fields.Many2one('uom.uom', string=_('Unit of Measure'))
    unit_price = fields.Float(string=_('Cost / Unit'), copy=False)
    total_cost = fields.Float(string=_('Total Cost'), compute='_compute_total_cost', store=True)
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

