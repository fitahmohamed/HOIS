# -*- coding: utf-8 -*-
'''
this model created for cost estimation for project by creating template used later on project
to create wbs
'''
from datetime import date
from odoo import models, fields, api, _
from odoo.exceptions import  UserError, ValidationError


class WbsJobCost(models.Model):
    _name = 'wbs.job.cost'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "WBS Costing"
    _rec_name = 'number'

    @api.model
    def create(self, vals_list):
        """Create a new 'wbs.job.cost' record with a unique number."""
        for vals in vals_list:
            number = self.env['ir.sequence'].next_by_code('wbs.job.cost')
            vals.update({
                'number': number,
            })
        return super(WbsJobCost, self).create(vals_list)

    def unlink(self):
        """
        Delete the current record if its state is 'draft'."""
        for rec in self:
            if rec.state not in ('draft'):
                raise ValidationError(_('You can not delete Job Cost Sheet which is not draft'))
        return super(WbsJobCost, self).unlink()

    @api.depends(
        'job_cost_line_ids',
        'job_cost_line_ids.qty',
        'job_cost_line_ids.unit_price',
    )
    def _compute_material_total(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.material_total = sum([(p.qty * p.unit_price) for p in rec.job_cost_line_ids])

    @api.depends(
        'job_labour_line_ids',
        'job_labour_line_ids.unit_price'
    )
    def _compute_labor_total(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.labor_total = sum([(p.qty * p.unit_price) for p in rec.job_labour_line_ids])

    @api.depends(
        'job_equipment_line_ids',
        'job_equipment_line_ids.qty',
        'job_equipment_line_ids.unit_price'
    )
    def _compute_equipment_total(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.equipment_total = sum([(p.qty * p.unit_price) for p in rec.job_equipment_line_ids])

    @api.depends(
        'job_expense_line_ids',
        'job_expense_line_ids.qty',
        'job_expense_line_ids.unit_price'
    )
    def _compute_expense_total(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.expense_total = sum([(p.qty * p.unit_price) for p in rec.job_expense_line_ids])

    @api.depends(
        'job_subcontractor_line_ids',
        'job_subcontractor_line_ids.qty',
        'job_subcontractor_line_ids.unit_price'
    )
    def _compute_subcontractor_total(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.subcontractor_total = sum([(p.qty * p.unit_price) for p in rec.job_subcontractor_line_ids])

    @api.depends(
        'material_total',
        'labor_total',
        'equipment_total',
        'expense_total',
        'subcontractor_total'
    )
    def _compute_jobcost_total(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.jobcost_total = rec.material_total + rec.labor_total + rec.equipment_total + rec.expense_total + rec.subcontractor_total


    def _job_costsheet_line_count(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.job_costsheet_line_count = self.env['wbs.job.cost.line'].search_count(
                    [('job_cost_id', '=', rec.id)])


    number = fields.Char( readonly=True, default='New', copy=False)
    name = fields.Char(required=True, copy=True, default='New',string=_('Name'))
    notes_job = fields.Text(required=False, copy=True, string=_('Job Cost Details'))
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, string=_('Created By'), readonly=True)
    description = fields.Char(string=_('Description'))
    currency_id = fields.Many2one('res.currency',string=_('Currency'),default=lambda self: self.env.user.company_id.currency_id,readonly=False)
    company_id = fields.Many2one('res.company',default=lambda self: self.env.company,string=_('Company'),readonly=True)
    ref_id = fields.Many2one('project.wbs.builds.line', string=_('Reference'),readonly=True, ondelete='cascade')
    material_total = fields.Float(string=_('Total Material Cost'), compute='_compute_material_total', store=True)
    labor_total = fields.Float(string=_('Total Labour Cost'), compute='_compute_labor_total', store=True )
    equipment_total = fields.Float(string=_('Total Equipment Cost'), compute='_compute_equipment_total', store=True)
    expense_total = fields.Float(string=_('Total Expenses Cost'), compute='_compute_expense_total', store=True)
    subcontractor_total = fields.Float(string=_('Total Subcontractor Cost'), compute='_compute_subcontractor_total', store=True)
    jobcost_total = fields.Float(string=_('Total Cost'), compute='_compute_jobcost_total', store=True)
    job_cost_line_ids = fields.One2many('wbs.job.cost.line', 'job_cost_id', string=_('Direct Materials'), copy=False, domain=[('flag', '=', 'm')])
    job_labour_line_ids = fields.One2many('wbs.job.cost.line', 'job_cost_id',string=_('Direct Labours'), copy=False, domain=[('flag', '=', 'l')])
    job_equipment_line_ids = fields.One2many('wbs.job.cost.line', 'job_cost_id',string=_('Direct Equipments'), copy = False, domain=[('flag', '=', 'q')])
    job_expense_line_ids = fields.One2many('wbs.job.cost.line', 'job_cost_id',string=_('Direct Expenses'), copy=False, domain=[('flag', '=', 'e')])
    job_subcontractor_line_ids = fields.One2many('wbs.job.cost.line', 'job_cost_id',string=_('Direct Subcontractor'), copy=False, domain=[('flag', '=', 's')])
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approve', 'Approved'),
        ],
        string='Status',
        track_visibility='onchange',
        default='draft',
    )

    job_costsheet_line_count = fields.Integer(
        compute='_job_costsheet_line_count'
    )

    employee_id = fields.Many2one('hr.employee',string= "Responsible Employee")
    department_id = fields.Many2one('hr.department',string= "Department")
    expected_date = fields.Date(string=_('Expected Date'))


    def action_draft(self):
        """Set the state to draft."""
        for rec in self:
            rec.write({
                'state': 'draft',
            })

    def action_confirm(self):
        """Set the state to approve."""
        for rec in self:
            rec.write({
                'state': 'approve',
            })

    def action_view_jobcost_sheet_lines(self):
        """
            Action to view job cost sheet lines associated with the current job cost sheet.
            return: Dictionary with information for the action.
            """
        jobcost_line = self.env['wbs.job.cost.line']
        cost_ids = jobcost_line.search([('job_cost_id', '=', self.id)]).ids
        action = self.env.ref('nthub_constructions.action_wbs_cost_line_custom').read()[0]
        action['domain'] = [('id', 'in', cost_ids)]
        ctx = 'context' in action and action['context'] and eval(action['context']).copy() or {}
        ctx.update(create=False)
        ctx.update(edit=False)
        ctx.update(delete=False)
        action['context'] = ctx
        return action


class WbsJobCostLine(models.Model):
    _name = 'wbs.job.cost.line'
    _inherit = 'analytic.mixin'
    _description = 'Job Cost Line'
    _rec_name = 'description'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """On change of product id set the values of description, qty, uom_id, unit_price"""
        for rec in self:
            rec.description = rec.product_id.name
            rec.qty = 1.0
            rec.uom_id = rec.product_id.uom_id.id
            rec.unit_price = rec.product_id.standard_price  # lst_price

    @api.onchange('cost_per_day', 'no_of_days')
    def _onchange_cost_per_day(self):
        """On change of cost per day set the values of unit_price"""
        for rec in self:
            rec.unit_price = rec.cost_per_day * rec.no_of_days

    @api.onchange('unit_price')
    def _onchange_unit_price(self):
        """On change of unit price set the values of unit_value"""
        for rec in self:
            rec.unit_value = rec.unit_price

    @api.depends('qty', 'unit_price', 'job_cost_id')
    def _compute_total_cost(self):
        """On change of unit price set the values of unit_value"""
        for rec in self:
            rec.total_cost = rec.qty * rec.unit_price

    job_cost_id = fields.Many2one('wbs.job.cost', string=_('Job Cost'), help='Job Costing')
    product_id = fields.Many2one('product.product', string=_('Product'), help='Product', copy=False, required=True)
    description = fields.Char(string=_('Description'), help='Description', copy=False)
    date = fields.Date(string=_('Date'), help='Date', required=True, default=fields.Date.today(), copy=False)
    qty = fields.Float(string=_('Planned Qty'), copy=False)
    uom_id = fields.Many2one('uom.uom', string=_('Unit of Measure'))
    unit_price = fields.Float(related='product_id.standard_price', string=_('Cost / Unit'), readonly=False, copy=False)
    unit_value = fields.Float(string=_('Value'))
    total_cost = fields.Float(string=_('Cost Price Sub Total'), compute='_compute_total_cost', store=True)
    currency_id = fields.Many2one('res.currency', string=_('Currency'),
                                  related='job_cost_id.currency_id', readonly=True)
    flag = fields.Selection(
        [('m', 'Material'), ('l', 'labour'), ('e', 'Expenses'), ('q', 'Equipment'), ('s', 'Subcontractor')],
        string=_('Type'), )
    cost_per_day = fields.Float(string=_('Cost per day'))
    no_of_days = fields.Integer(string=_('No of days'))

    budget_amount = fields.Float(string='Budget Amount', compute='_compute_budget_amount', store=True)

    @api.depends('analytic_distribution')
    def _compute_budget_amount(self):
        """
            Computes the budget amount based on analytic distribution.
        """
        for rec in self:
            budget_amount = 0
            if rec.analytic_distribution:
                for key, value in rec.analytic_distribution.items():
                    analytic_account = self.env['account.analytic.account'].browse(int(key.split(",")[0]))
                    budget_line_ids = self.env['budget.line'].search([('account_id', '=', analytic_account.id)])
                    for budget_item in budget_line_ids:
                        budget_amount += budget_item.budget_amount * value / 100
                rec.budget_amount = budget_amount
            else:
                rec.budget_amount = 0
