from odoo import models, fields, api, _


class ProjectWbs(models.Model):
    _name = 'project.wbs'
    _description = 'project wbs'
    _rec_name = "name"

    name = fields.Char(string=_('Reference'), default='New', copy=False, readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'), ('cancel', 'Cancel')],
                             default='draft', string=_('Status'))
    customer_id = fields.Many2one('res.partner', string=_('Customer'), required=True)
    project_id = fields.Many2one("project.project", string=_("Project"), readonly=True)
    date = fields.Date(default=fields.Date.context_today, string=_('Date'))
    project_wbs_builds_ids = fields.One2many('project.wbs.builds', 'project_wbs_id', string=_('Project WBS Builds'))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string=_('Company'))
    currency_id = fields.Many2one('res.currency', string=_('Currency'))

    def action_confirm(self):
        self.state = 'confirm'
        for build in self.project_wbs_builds_ids:
            build.action_approved()
            self.project_id.wbs_state = True

    def action_draft(self):
        self.state = 'draft'
        self.project_id.wbs_state = False



class ProjectBuilds(models.Model):
    _name = 'project.wbs.builds'
    _description = 'project wbs builds'
    _rec_name = "name"

    project_wbs_id = fields.Many2one('project.wbs', string=_('Project Wbs'), ondelete='cascade')
    project_wbs_builds_line_ids = fields.One2many('project.wbs.builds.line', 'project_wbs_builds_id',
                                                  string=_('Project Wbs Builds Lines'))
    name = fields.Char(string=_('Reference'), default='New', copy=False,readonly=True)
    customer_id = fields.Many2one('res.partner', string=_('Customer'))
    project_id = fields.Many2one("project.project", string=_("Project"))
    Project_Task_id = fields.Many2one("project.task", string=_("Project Task"))
    company_id = fields.Many2one('res.company', related='project_wbs_id.company_id', string=_('Company'))
    currency_id = fields.Many2one('res.currency', related='project_wbs_id.currency_id', string=_('Currency'))
    total_cost = fields.Float(string=_('Total Cost'), compute='_compute_total_cost')
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved')], default='draft')

    def action_approved(self):
        self.state = "approved"

    @api.depends('project_wbs_builds_line_ids.sub_total', 'project_wbs_builds_line_ids.item_id')
    def _compute_total_cost(self):
        """
        Compute the total cost for each record by summing up the sub_total values of related line items.
        """
        for record in self:
            record.total_cost = sum(line.sub_total for line in record.project_wbs_builds_line_ids)


class ProjectWbsLine(models.Model):
    _name = 'project.wbs.builds.line'
    _description = 'project wbs builds line'

    project_wbs_builds_id = fields.Many2one('project.wbs.builds', string=_('Project Wbs'), ondelete='cascade')
    item_id = fields.Many2one('tender.item', string=_('Item'), help='Item')
    name = fields.Char(string=_('Description'))
    uom_id = fields.Many2one('uom.uom', string=_('Unit of Measure'))
    qty = fields.Float(string=_('Quantity'), default=0.0)
    unit_price = fields.Float(string=_('Unit Price'), compute='_compute_unit_price', store=True)
    sub_total = fields.Float(string=_('Subtotal'), compute='_compute_sub_total')
    flag = fields.Selection(
        [('m', 'Material'), ('l', 'labour'), ('e', 'Expenses'), ('q', 'Equipment'), ('s', 'subcontractor')],
        string=_('Type'))
    company_id = fields.Many2one('res.company', related='project_wbs_builds_id.company_id', string=_('Company'))
    currency_id = fields.Many2one('res.currency', related='project_wbs_builds_id.currency_id', string=_('Currency'))
    template_id = fields.Many2one('wbs.job.cost', string=_("Template"))

    @api.depends('template_id', 'template_id.jobcost_total')
    def _compute_unit_price(self):
        """
        Compute the unit price based on the selected template's jobcost_total.
        """
        for record in self:
            record.unit_price = record.template_id.jobcost_total

    @api.depends('item_id', 'qty', 'unit_price')
    def _compute_sub_total(self):
        """
        Compute the subtotal based on the quantity and unit price.
        """
        for record in self:
            record.sub_total = record.qty * record.unit_price

    @api.onchange('item_id')
    def _onchange_item_id(self):
        """
        Set the name and uom_id fields based on the selected item.
        """
        for rec in self:
            rec.name = rec.item_id.name
            rec.qty = 1.0
            rec.uom_id = rec.item_id.uom_id.id


