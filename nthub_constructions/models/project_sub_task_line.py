# -*- coding: utf-8 -*-
'''
this model created for cost estimation for project by creating template used later on project
to create wbs
'''
from datetime import date
from odoo import models, fields, api, _
from odoo.exceptions import  UserError, ValidationError


class ProjectSubTaskLine(models.Model):
    _name = 'project.sub.task.line'
    _inherit = 'analytic.mixin'


    # domain=lambda self: self._get_product_domain()
    product_id = fields.Many2one('product.product', string=_('Product'),)
    date = fields.Date(string=_('Date'), help='Date', default=lambda self: fields.Datetime.now(), copy=False)
    qty = fields.Float(string=_('Planned Qty'), copy=False)

    flag = fields.Selection(
        [('m', 'Material'), ('l', 'labour'), ('e', 'Expenses'), ('q', 'Equipment'), ('s', 'Subcontractor')],
        string=_('Type'), )


    budget_amount = fields.Float(string='Budget Amount', compute='_compute_analytic_distribution', store=True)

    employee_id = fields.Many2many('hr.employee', string=_('Employee'))

    task_id =fields.Many2one('project.task', string=_('Task'))     

    check_state = fields.Selection(
        [('in', 'check_in'), ('out', 'check_out'), ('done', 'done')] , default='in')

    check_start = fields.Selection(
        [('st', 'Start'), ('out', 'Out'), ('done', 'Done')] , default='st')

    start = fields.Datetime(string=_('Start Date'), copy=False)
    end = fields.Datetime(string=_('End Date'), copy=False)

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        related='task_id.project_id',
        store=True,  # Optional: Set to True if you want this field to be stored in the database
        readonly=True
    )
    parent_id = fields.Many2one(
        'project.task',
        string='Parent',
        related='task_id.parent_id',
        store=True,  # Optional: Set to True if you want this field to be stored in the database
        readonly=True
    )
    
        


    def start_date(self):
        self.start = fields.Datetime.now()
        self.check_start = 'out'


    def end_date(self):
        self.end = fields.Datetime.now()
        self.check_start = 'done'

        
    @api.depends('analytic_distribution')
    def _compute_analytic_distribution(self):
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

    def check_in_attend(self):
        """Checks in all employees in the employee_ids field."""
        Attendance = self.env['hr.attendance']
        for employee in self.employee_id:
            # Get the last attendance record for the employee
            today = fields.Date.today()
            start_of_day = f"{today} 00:00:00"
            end_of_day = f"{today} 23:59:59"
            last_attendance = Attendance.search([('employee_id', '=', employee.id),('check_in', '<', end_of_day ),('check_in', '>', start_of_day )], limit=1, order='check_in desc')

            # Check if the employee is already checked in
            if last_attendance:
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id,
                    'simple_notification',
                    {
                        'title': _("Warning"),
                        'message': _("Employee %s is already in" % employee.name),
                        'sticky': True,
                        'type': 'warning'
                    }
                )
                continue

            # Create a new check-in record
            Attendance.create({
                'employee_id': employee.id,
                'check_in': fields.Datetime.now(),
            })

        self.check_state = 'out'


    def check_out_attend(self):
        """Checks out all employees in the employee_ids field."""
        Attendance = self.env['hr.attendance']
        for employee in self.employee_id:
            # Get the last attendance record for the employee
            today = fields.Date.today()
            start_of_day = f"{today} 00:00:00"
            end_of_day = f"{today} 23:59:59"
            last_attendance = Attendance.search([('employee_id', '=', employee.id),('check_in', '<', end_of_day ),('check_in', '>', start_of_day )], limit=1, order='check_in desc')

            # Check if the employee is already checked out
            if not last_attendance or last_attendance.check_out:
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id,
                    'simple_notification',
                    {
                        'title': _("Warning"),
                        'message': _("Employee %s is already checked out." % employee.name),
                        'sticky': True,
                        'type': 'warning'
                    }
                )
                continue

            # Update the check-out time
            last_attendance.write({
                'check_out': fields.Datetime.now(),
            })

        self.check_state = 'done'


   
   

