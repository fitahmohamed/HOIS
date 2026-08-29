# -*- coding: utf-8 -*-
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class Project(models.Model):
    _inherit = 'project.project'

    state = fields.Selection(
        [('draft', 'Draft'), ('tender', 'Tendering'), ('contract', 'Contracted'),
         ('done', 'Done')], string=_('Status'), default='draft')
    wbs_count = fields.Integer(string=_('WBS'), compute='get_wbs_count')
    task_count = fields.Integer(string=_('Tasks'), compute='get_task_count')
    sub_task_count = fields.Integer(string=_('Tasks'), compute='get_sub_task_count')
    contract_count = fields.Integer(string=_('Contract'), compute='get_contract_count')
    currency_id = fields.Many2one('res.currency')
    is_tender = fields.Boolean(string=_("Tender"))
    approved_tender = fields.Boolean(string=_("Approved Tender"))
    num_of_units = fields.Integer(string=_('Number of Units'), required=True, default=1)
    tender_creation_date = fields.Date(string=_("Tender Creation Date"), default=fields.Date.today())
    tender_approval_date = fields.Date(string=_('Tender Approval Date'))
    contract_date = fields.Date(string=_('Contract Date'))
    wbs_creation_date = fields.Date(string=_('Wbs Creation Date'))
    tasks_generation_date = fields.Date(string=_('Tasks Generation Date'))
    completion_request_count = fields.Integer(string=_('Completion Requests'), compute='get_completion_request_count')
    total_amount = fields.Monetary(string=_('Total Amount'), compute='get_total_amount')
    project_end_date = fields.Datetime(string=_('Project End Date'))
    total_extra_cost = fields.Float(string=_("Total Extra Cost"))
    project_extras_ids = fields.One2many('project.extras', 'project_id', string=_("Extras"))
    images_ids = fields.One2many("project.images", "project_id")
    documents_ids = fields.One2many("project.documents", "project_id")
    engineers_ids = fields.Many2many("hr.employee")
    stack_holders_ids = fields.Many2many("res.partner")
    project_issue_ids = fields.One2many('project.issue.track', 'project_id', string=_('project Issue'), copy=True)
    contract_id = fields.Many2one("owner.contract", string=_("Contract"))
    contract_state = fields.Selection(
        related='contract_id.state',
        string=_("Contract State"),
        store=True
    )
    wbs_state = fields.Boolean(string=_("Wbs State"), default=False)


    @api.depends()
    def get_total_amount(self):
        for rec in self:
            contracts = rec.env['owner.contract'].search([
                ('project_id', '=', rec.id), ('is_owner', '=', True), ('state', '=', 'contract')],limit=1)
            rec.total_amount = contracts.total_after_deduction_allowance

    def unlink(self):
        """
        Delete the current record if its state is 'draft' or 'tender'.

        :return: bool
            Returns True if the record is successfully deleted, otherwise raises an exception.
        """
        for rec in self:
            if rec.state not in ['draft', 'tender']:
                raise UserError(_('You can not delete a project which is in %s state.') % rec.state)
            return super(Project, rec).unlink()

    @api.onchange('num_of_units')
    def _onchange_num_of_units(self):
        if self.num_of_units < 1:
            # Set the value to at least 1
            self.num_of_units = 1

    def create_contract(self):
        """This method confirms the tender and updates the state of the project to 'contract'."""
        for project in self:
            if not project.partner_id:
                raise UserError(_('Please select a customer.'))
            if project.is_tender == False:
                project.write({'state': 'contract'})
                project.approved_tender = True
                contract_vals = {
                    'project_id': project.id,
                    'partner_id': project.partner_id.id,
                    'date': datetime.date.today(),
                    'received_date': datetime.date.today(),
                    'currency_id': project.currency_id.id,
                    'is_owner': True,
                }
                contract = self.env['owner.contract'].create(contract_vals)
                project.contract_id = contract.id

        return True

    def get_contract_count(self):
        for rec in self:
            contracts = rec.env['owner.contract'].search([
                ('project_id', '=', rec.id), ('is_owner', '=', True)])
            rec.contract_count = len(contracts)

    def action_open_contract(self):
        contracts = self.env['owner.contract'].search([('project_id', '=', self.id), ('is_owner', '=', True)])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Contract',
            'res_model': 'owner.contract',
            'view_type': 'form',
            'view_mode': 'form',
            'domain': [('id', 'in', contracts.ids)],
            'res_id': contracts.ids[0],
            'target': 'current',
        }

    def action_create_wbs(self):
        self.write({'wbs_creation_date': fields.Date.today()})
        return {
            'name': "WBS",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'new.wbs.wizard',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_project_id': self.id,
            },
            'target': 'new'
        }

    def get_wbs_count(self):
        wbs = self.env['project.wbs'].search([('project_id', '=', self.id)])
        self.wbs_count = len(wbs)

    def action_open_wbs(self):
        wbs = self.env['project.wbs'].search([('project_id', '=', self.id)])

        return {
            'name': _('WBS'),
            'domain': [('id', 'in', wbs.ids)],
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'project.wbs',
            'type': 'ir.actions.act_window',
            'res_id': wbs.ids[0],
            'target': 'current',
        }

    def action_view_Consumables(self):
        return {
            'name': 'Project Sub Task Lines (Domained)',
            'type': 'ir.actions.act_window',
            'res_model': 'project.sub.task.line',
            'view_mode': 'list,pivot',
            'context': {
                'group_by': ['task_id', 'parent_id','product_id']
            },
            'domain': [('project_id', '=', self.id)],
        }

    def action_create_task(self):
        for rec in self:
            builds = self.env['project.wbs.builds'].search([
                ('project_wbs_id.project_id', '=', rec.id)
            ])
            for b in builds:
                parent_task = self.env['project.task'].create({
                    'project_id': rec.id,
                    'project_wbs_id': b.project_wbs_id.id,
                    'wbs_builds_id': b.id,
                    'name': b.name,
                })
                b.Project_Task_id = parent_task
                for i in b.project_wbs_builds_line_ids:
                    self.env['project.task'].create({
                        'project_id': rec.id,
                        'name': i.name,
                        'parent_id': parent_task.id,
                        'item_wbs_builds_line_id': i.id,
                        'template_wbs_builds_line_id': i.template_id.id,
                        'product_sub_task_ids': [(0, 0, {
                            'product_id': line.product_id.id,
                            'quantity': line.qty * i.qty,
                            'analytic_distribution': line.analytic_distribution or {},
                        }) for line in i.template_id.job_cost_line_ids],
                    })
        return True

    def get_task_count(self):
        for rec in self:
            tasks = self.env['project.task'].search([('project_id', '=', rec.id), ('parent_id', '=', False)])
            rec.task_count = len(tasks)

    def get_sub_task_count(self):
        for rec in self:
            tasks = self.env['project.task'].search([('project_id', '=', rec.id), ('parent_id', '!=', False)])
            rec.sub_task_count = len(tasks)

    def action_open_tasks(self):
        return {
            'name': _('Tasks'),
            'domain': [('project_id', '=', self.id),('parent_id', '=', False)],
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
    def action_open_sub_tasks(self):
        return {
            'name': _('Tasks'),
            'domain': [('project_id', '=', self.id),('parent_id', '!=', False)],
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'group_by': ['parent_id']
                 # 'search_default_stage': True
            },
        }

    def action_open_completion_request(self):
        completion_request_model = self.env['project.completion.request']
        completion_requests = completion_request_model.search([('project_id', '=', self.id)])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Completion Templates',
            'res_model': 'project.completion.request',
            'view_mode': 'list,form',
            'domain': [('id', 'in', completion_requests.ids)],
            'target': 'current',
        }

    def get_completion_request_count(self):
        for rec in self:
            requests = rec.env['project.completion.request'].search([
                ('project_id', '=', rec.id)
            ])
            rec.completion_request_count = len(requests)

    def action_done(self):
        """
        This function completes the action and checks for completion and delivery requests,
        raising errors if any are found. It then updates the state to 'done' and sets the
        project end date to the current datetime.
        """
        for rec in self:
            comp_requests = rec.env['project.completion.request'].search([
                ('project_id', '=', rec.id), ('state', 'in', ['draft', 'processing'])
            ])
            sub_delivery_requests = rec.env['subcontractor.delivery.request'].search([
                ('project_id', '=', rec.id), ('state', '=', 'draft')
            ])
            if comp_requests:
                raise UserError(_('You can not End the project which has completion requests in draft or processing state.'))
            elif sub_delivery_requests:
                raise UserError(_('You can not End the project which has Sub-contract delivery requests in draft state.'))
            else:
                rec.state = 'done'
                rec.project_end_date = datetime.datetime.now()

class Image(models.Model):
    _name = 'project.images'
    _description = "project.images"

    name = fields.Char(string=_("Name"), required=True)
    image = fields.Image()
    project_id = fields.Many2one("project.project")


class Document(models.Model):
    _name = 'project.documents'
    _description = "project.document"

    name = fields.Char(string=_("Name"), required=True)
    binary = fields.Binary()
    project_id = fields.Many2one("project.project")


class Issue(models.Model):
    _name = 'project.issue'
    _description = "project.issue"

    name = fields.Char(string=_("Name"), required=True)
    description = fields.Text()


class IssueTrack(models.Model):
    _name = 'project.issue.track'
    _description = "project.issue.track"

    name = fields.Char(string=_("Name"), required=True)
    category = fields.Many2one("project.issue")
    date = fields.Date(default=fields.Date.context_today)
    description = fields.Text(string="Description")
    project_id = fields.Many2one("project.project")
