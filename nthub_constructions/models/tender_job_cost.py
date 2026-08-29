# -*- coding: utf-8 -*-
'''
this model created for cost estimation for project by creating template used later on project
to create tender
'''

from datetime import date
from email.policy import default

from odoo import models, fields, api, _
from odoo.exceptions import  UserError, ValidationError


class TenderJobCosting(models.Model):
    _name = 'tender.job.cost'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Job Costing"
    _rec_name = 'number'

    @api.model
    def create(self,  vals_list):
        """Create a new 'tender.job.cost' record with a unique name."""
        for vals in vals_list:
            number = self.env['ir.sequence'].next_by_code('tender.job.cost')
            vals.update({
                'number': number,
            })
        return super(TenderJobCosting, self).create(vals)

    def unlink(self):
        """
        Delete the current record if its state is 'draft' or 'cancel'."""
        for rec in self:
            if rec.state not in ('draft', 'cancel'):
                raise ValidationError(_('You can not delete Job Cost Sheet which is not draft or cancelled.'))
        return super(TenderJobCosting, self).unlink()

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


    @api.depends('job_deduction_line_ids', 'job_deduction_line_ids.qty', 'job_deduction_line_ids.unit_price')
    def _compute_deduction_total(self):
        for rec in self:
            rec.deduction_total = sum(p.qty * p.unit_price for p in rec.job_deduction_line_ids)

    @api.depends('job_allowance_line_ids', 'job_allowance_line_ids.qty', 'job_allowance_line_ids.unit_price')
    def _compute_allowance_total(self):
        for rec in self:
            rec.allowance_total = sum(p.qty * p.unit_price for p in rec.job_allowance_line_ids)

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
            rec.job_costsheet_line_count = self.env['tender.job.cost.line'].search_count(
                [('job_cost_id', '=', rec.id)])

    @api.depends(
        'job_cost_line_ids', 'job_cost_line_ids.qty', 'job_cost_line_ids.cost_actual',
        'job_labour_line_ids', 'job_labour_line_ids.qty', 'job_labour_line_ids.cost_actual',
        'job_equipment_line_ids', 'job_equipment_line_ids.qty', 'job_equipment_line_ids.cost_actual',
        'job_expense_line_ids', 'job_expense_line_ids.qty', 'job_expense_line_ids.cost_actual',
        'job_subcontractor_line_ids', 'job_subcontractor_line_ids.qty', 'job_subcontractor_line_ids.cost_actual',
    )
    def _compute_actual_total(self):
        """Compute actual cost for all lines types"""
        self.actual_total = 0
        for rec in self:
            rec.actual_total += sum([(p.qty * p.cost_actual) for p in rec.job_cost_line_ids])
            rec.actual_total += sum([(p.qty * p.cost_actual) for p in rec.job_labour_line_ids])
            rec.actual_total += sum([(p.qty * p.cost_actual) for p in rec.job_equipment_line_ids])
            rec.actual_total += sum([(p.qty * p.cost_actual) for p in rec.job_expense_line_ids])
            rec.actual_total += sum([(p.qty * p.cost_actual) for p in rec.job_subcontractor_line_ids])

    @api.depends('jobcost_total', 'actual_total', )
    def _compute_revenue(self):
        """Compute final revenue"""
        for rec in self:
            rec.revenue = rec.jobcost_total - rec.actual_total

    # ── بيانات البند المرتبط من المناقصة ──────────────────────────────────
    tender_item_name  = fields.Char(string=_('Tender Item Name'),      copy=False)
    tender_item_desc  = fields.Char(string=_('Description'),          copy=False)
    tender_item_qty   = fields.Float(string=_('Quantity'),        copy=False)
    tender_item_uom_id = fields.Many2one('uom.uom', string=_('Unit of Measure'), copy=False)

    number = fields.Char(readonly=True, default='New', copy=False)
    name = fields.Char(required=True, copy=True, default='New', string=_('Name'))
    notes_job = fields.Text(required=False, copy=True, string=_('Job Cost Details'))
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, string=_('Created By'), readonly=True)
    description = fields.Char(string=_('Description'))
    currency_id = fields.Many2one('res.currency', string=_('Currency'),
                                  default=lambda self: self.env.user.company_id.currency_id, readonly=False)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string=_('Company'),
                                 readonly=True)

    material_total = fields.Float(string=_('Total Material'), compute='_compute_material_total', store=True)
    labor_total = fields.Float(string=_('Total Labour'), compute='_compute_labor_total', store=True)
    equipment_total = fields.Float(string=_('Total Equipment'), compute='_compute_equipment_total', store=True)
    expense_total = fields.Float(string=_('Total Expenses'), compute='_compute_expense_total', store=True)
    subcontractor_total = fields.Float(string=_('Total Subcontractor'), compute='_compute_subcontractor_total', store=True)
    jobcost_total = fields.Float(string=_('Total Cost'), compute='_compute_jobcost_total', store=True)
    actual_total = fields.Float(string=_('Total Actual Cost'), compute='_compute_actual_total', store=True,
                                readonly=True)
    revenue = fields.Float(string=_('Revenue'), compute='_compute_revenue', store=True, readonly=True)
    job_cost_line_ids = fields.One2many('tender.job.cost.line', 'job_cost_id', string=_('Direct Materials'), copy=True,
                                        domain=[('flag', '=', 'm')])
    job_labour_line_ids = fields.One2many('tender.job.cost.line', 'job_cost_id', string=_('Direct Labours'), copy=True,
                                          domain=[('flag', '=', 'l')])
    job_equipment_line_ids = fields.One2many('tender.job.cost.line', 'job_cost_id', string=_('Direct Equipments'),
                                             copy=True, domain=[('flag', '=', 'q')])
    job_expense_line_ids = fields.One2many('tender.job.cost.line', 'job_cost_id', string=_('Direct Expenses'),
                                           copy=True, domain=[('flag', '=', 'e')])
    job_deduction_line_ids   = fields.One2many('tender.job.cost.line', 'job_cost_id',
                                                   string=_('Deductions'), copy=True,
                                                   domain=[('flag', '=', 'd')])
    job_allowance_line_ids   = fields.One2many('tender.job.cost.line', 'job_cost_id',
                                                   string=_('Allowances'), copy=True,
                                                   domain=[('flag', '=', 'a')])
    deduction_total  = fields.Float(string=_('Deduction Total'),
                                    compute='_compute_deduction_total', store=True)
    allowance_total  = fields.Float(string=_('Allowance Total'),
                                    compute='_compute_allowance_total', store=True)

    job_subcontractor_line_ids = fields.One2many('tender.job.cost.line', 'job_cost_id',
                                                 string=_('Direct Subcontractor'), copy=True,
                                                 domain=[('flag', '=', 's')])

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approve', 'Approved'),
            ('cancel', 'Canceled'),
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

    def action_draft(self):
        """Set the state to draft."""
        for rec in self:
            rec.write({
                'state': 'draft',
            })

    # @api.multi
    # def action_confirm(self):
    #     for rec in self:
    #         rec.write({
    #             'state': 'confirm',
    #         })

    def action_approve(self):
        """Set the state to approve."""
        for rec in self:
            rec.write({
                'state': 'approve',
            })

    # @api.multi
    def action_cancel(self):
        """Set the state to cancel."""
        for rec in self:
            rec.write({
                'state': 'cancel',
            })

    # @api.multi
    # def action_view_purchase_order_line(self):
    #     self.ensure_one()
    #     purchase_order_lines_obj = self.env['purchase.order.line']
    #     cost_ids = purchase_order_lines_obj.search([('job_cost_id', '=', self.id)]).ids
    #     action = {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Purchase Order Line',
    #         'res_model': 'purchase.order.line',
    #         'res_id': self.id,
    #         'domain': "[('id','in',[" + ','.join(map(str, cost_ids)) + "])]",
    #         'view_type': 'form',
    #         'view_mode': 'list,form',
    #         'target': self.id,
    #     }
    #     return action

    # @api.multi
    # def action_view_hr_timesheet_line(self):
    #     hr_timesheet = self.env['account.analytic.line']
    #     cost_ids = hr_timesheet.search([('job_cost_id', '=', self.id)]).ids
    #     action = self.env.ref('hr_timesheet.act_hr_timesheet_line').read()[0]
    #     action['domain'] = [('id', 'in', cost_ids)]
    #     return action

    def action_view_jobcost_sheet_lines(self):
        """
            Action to view job cost sheet lines associated with the current job cost sheet.
            return: Dictionary with information for the action.
            """
        jobcost_line = self.env['tender.job.cost.line']
        cost_ids = jobcost_line.search([('job_cost_id', '=', self.id)]).ids
        action = self.env.ref('nthub_constructions.action_job_cost_line_custom').read()[0]
        action['domain'] = [('id', 'in', cost_ids)]
        ctx = 'context' in action and action['context'] and eval(action['context']).copy() or {}
        ctx.update(create=False)
        ctx.update(edit=False)
        ctx.update(delete=False)
        action['context'] = ctx
        return action

    # @api.multi
    # def action_view_vendor_bill_line(self):
    #     #        account_invoice_lines_obj = self.env['account.invoice.line']
    #     account_invoice_lines_obj = self.env['account.move.line']
    #     cost_ids = account_invoice_lines_obj.search([('job_cost_id', '=', self.id)]).ids
    #     action = {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Account Invoice Line',
    #         #            'res_model': 'account.invoice.line',
    #         'res_model': 'account.move.line',
    #         'res_id': self.id,
    #         'domain': "[('id','in',[" + ','.join(map(str, cost_ids)) + "])]",
    #         'view_type': 'form',
    #         'view_mode': 'list,form',
    #         'target': self.id,
    #     }
    #     action['context'] = {
    #         'create': False,
    #         'edit': False,
    #     }
    #     return action


class TenderJobCostLine(models.Model):
    _name = 'tender.job.cost.line'
    _inherit = 'analytic.mixin'
    _description = 'Job Cost Line'
    _rec_name = 'description'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """
        Set the default description and unit price for the selected product.
        """
        for rec in self:
            rec.description = rec.product_id.name
            rec.qty = 1.0
            rec.uom_id = rec.product_id.uom_id.id
            rec.unit_price = rec.product_id.standard_price  # lst_price

    @api.onchange('cost_per_day', 'no_of_days')
    def _onchange_cost_unit_price(self):
        """
        Set the unit price based on the cost per day and number of days.
        """
        for rec in self:
            rec.unit_price = rec.cost_per_day * rec.no_of_days

    @api.onchange('product_id')
    def _onchange_cost_actual(self):
        """ Set the cost_actual based on the cost of product. """
        for rec in self:
            rec.cost_actual =  rec.product_id.standard_price

    @api.onchange('product_id')
    def _onchange_cost_per_day(self):
        """
        Set the unit price based on the cost per day and number of days.
        """
        for rec in self:
            rec.cost_per_day = rec.product_id.lst_price

    @api.depends('qty', 'unit_price')
    def _compute_total_cost(self):
        """
        Compute the total cost based on the quantity and unit price.
        """
        for rec in self:
            rec.total_cost = rec.qty * rec.unit_price

    job_cost_id = fields.Many2one('tender.job.cost', string=_('Job Cost'), help='Job Costing', ondelete='cascade')
    product_id   = fields.Many2one('product.product', string=_('Product'), help='Product', copy=False, required=True)
    product_code = fields.Char(related='product_id.default_code', string=_('Code'), readonly=True, store=False)
    description  = fields.Char(string=_('Description'), help='Description', copy=False)
    date = fields.Date(string=_('Date'), help='Date', required=True, default=fields.Date.today(), copy=False)
    qty = fields.Float(string=_('Planned Qty'), copy=False)
    uom_id = fields.Many2one('uom.uom', string=_('Unit of Measure'))
    unit_price = fields.Float(string=_('Price / Unit'), readonly=False, copy=False)
    cost_actual = fields.Float(string=_('Cost Actual'), readonly=False, copy=False)
    # actual_price = fields.Float(related='product_id.standard_price', string=_('Cost'), readonly=False, copy=False,
    #                             invisible=True)
    total_cost = fields.Float(string=_('Cost Price Sub Total'), compute='_compute_total_cost', store=True)
    currency_id = fields.Many2one('res.currency', string=_('Currency'),
                                  related='job_cost_id.currency_id', readonly=True)
    flag = fields.Selection(
        [('m', 'Material'), ('l', 'Labour'), ('e', 'Expenses'), ('q', 'Equipment'), ('s', 'Subcontractor'), ('d', 'Deduction'), ('a', 'Allowance')],
        string=_('Type'), required=True, )
    cost_per_day = fields.Float(string=_('Cost per day'))
    no_of_days = fields.Integer(string=_('No of days'),default=1)

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
