from odoo import models, fields, api, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    project_wbs_id = fields.Many2one("project.wbs", string=_("Project WBS"))
    wbs_builds_id = fields.Many2one("project.wbs.builds", string=_("Project WBS line"))
    item_wbs_builds_line_id = fields.Many2one("project.wbs.builds.line", string=_("Item WBS Builds Line"))
    template_wbs_builds_line_id = fields.Many2one("wbs.job.cost", string=_("Template WBS Builds Line"))
    product_sub_task_ids = fields.One2many("product.sub.task", 'project_task_id', string=_("Product Sub Task"))
    comp_request = fields.Many2one("project.completion.request", string=_("Completion Request"))
    location_dest_id = fields.Many2one(comodel_name='stock.location', string=_('Destination Location'))
    picking_type_id = fields.Many2one(comodel_name='stock.picking.type', string=_('Operation Type'))
    picking_count = fields.Integer(string=_('Picking Count'), compute='_compute_picking_count')
    stock_picking_ids = fields.One2many("stock.picking", 'project_task_id', string=_("Stock Picking"))
    job_material_line_ids = fields.One2many('project.sub.task.line', 'task_id', string=_('Direct Materials'),
                                            copy=False, domain=[('flag', '=', 'm')])
    job_labour_line_ids = fields.One2many('project.sub.task.line', 'task_id', string=_('Direct Labours'), copy=False,
                                          domain=[('flag', '=', 'l')])
    job_equipment_line_ids = fields.One2many('project.sub.task.line', 'task_id', string=_('Direct Equipments'),
                                             copy=False, domain=[('flag', '=', 'q')])
    job_expense_line_ids = fields.One2many('project.sub.task.line', 'task_id', string=_('Direct Expenses'), copy=False,
                                           domain=[('flag', '=', 'e')])
    job_subcontractor_line_ids = fields.One2many('project.sub.task.line', 'task_id', string=_('Direct Subcontractor'),
                                                 copy=False, domain=[('flag', '=', 's')])

    def create_comp_request(self):
        """Create a completion request based on the owner contract."""
        completion_request_model = self.env['project.completion.request']
        # Collect information from all contract lines
        completion_request_lines = []
        for rec in self:
            if rec.comp_request or rec.state not in ['1_done', '03_approved']:
                continue
            else:
                for line in rec.item_wbs_builds_line_id:
                    # contract = self.env['owner_contract_line'].search([('item_id', '=', line.id)])
                    line_data = {
                        'item_id': line.item_id.id,
                        'quantity': line.qty,
                        'description': line.name,#'Combined Data',
                        'price_unit': line.item_id.related_product_id.lst_price,
                        'uom_id': line.uom_id.id,
                        'percentage': 0,
                        'state': ' ',
                    }
                    completion_request_lines.append((0, 0, line_data))
        if line_data:
            # Create a completion request with the collected data
            completion_request_vals = {
                'contract_id': rec.project_id.contract_id.id,
                'type': 'initial',
                'state': 'processing',
                'project_id': rec.project_id.id,
                'date': fields.date.today(),
                'reference': rec.name,
                'line_ids': completion_request_lines,
            }
            comple_request = completion_request_model.create(completion_request_vals)
            rec.comp_request = comple_request.id
            return {
                'name': _('Completion Request'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'project.completion.request',
                "res_id": comple_request.id,
                'type': 'ir.actions.act_window',
                'target': 'current'
            }

    def action_open_material_form(self):
        self.ensure_one()
        job_cost_lines = self.env['wbs.job.cost.line'].search([
                ('job_cost_id', '=', self.template_wbs_builds_line_id.id)
        ])

        # Extract product IDs associated with this job_cost_id
        product_ids = job_cost_lines.mapped('product_id').ids

        context = {
                'default_task_id': self.id,
                'default_flag': 'm',
                'default_prod_tem_ids': product_ids
        }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Material',
            'view_mode': 'form',
            'res_model': 'project.sub.task.line',
            'target': 'new',
            'context': context,
        }

    def action_open_labour_form(self):
        self.ensure_one()
        job_cost_lines = self.env['wbs.job.cost.line'].search([
                ('job_cost_id', '=', self.template_wbs_builds_line_id.id)
        ])
        # Extract product IDs associated with this job_cost_id
        product_ids = job_cost_lines.mapped('product_id').ids

        context = {
                'default_task_id': self.id,
                'default_flag': 'l',
                'default_prod_tem_ids': product_ids
        }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Labour',
            'view_mode': 'form',
            'res_model': 'project.sub.task.line',
            'target': 'new',
            'context': context,
        }

    def action_open_expenses_form(self):
        self.ensure_one()
        job_cost_lines = self.env['wbs.job.cost.line'].search([
                ('job_cost_id', '=', self.template_wbs_builds_line_id.id)
        ])
        # Extract product IDs associated with this job_cost_id
        product_ids = job_cost_lines.mapped('product_id').ids

        context = {
                'default_task_id': self.id,
                'default_flag': 'e',
                'default_prod_tem_ids': product_ids
        }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Expenses',
            'view_mode': 'form',
            'res_model': 'project.sub.task.line',
            'target': 'new',
            'context': context,
        }

    def action_open_equipment_form(self):
        self.ensure_one()
        job_cost_lines = self.env['wbs.job.cost.line'].search([
                ('job_cost_id', '=', self.template_wbs_builds_line_id.id)
        ])
        # Extract product IDs associated with this job_cost_id
        product_ids = job_cost_lines.mapped('product_id').ids

        context = {
                'default_task_id': self.id,
                'default_flag': 'q',
                'default_prod_tem_ids': product_ids
        }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Equipment',
            'view_mode': 'form',
            'res_model': 'project.sub.task.line',
            'target': 'new',
            'context': context,
        }

    def action_open_subcontract_form(self):
        self.ensure_one()
        job_cost_lines = self.env['wbs.job.cost.line'].search([
                ('job_cost_id', '=', self.template_wbs_builds_line_id.id)
        ])
        # Extract product IDs associated with this job_cost_id
        product_ids = job_cost_lines.mapped('product_id').ids

        context = {
                'default_task_id': self.id,
                'default_flag': 's',
                'default_prod_tem_ids': product_ids
        }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Subcontract',
            'view_mode': 'form',
            'res_model': 'project.sub.task.line',
            'target': 'new',
            'context': context,
        }

    def _compute_picking_count(self):
        """ Compute incoming picking count."""
        for rec in self:
            rec.picking_count = len(rec.stock_picking_ids)

    def action_open_sub_task_wizard(self):
        """ Open Sub Task Wizard """
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transfer stock'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sub.task.wizard',
            'target': 'new',
        }

    def action_open_stock_picking(self):
        """ Open Stock Picking """
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('project_task_id', '=', self.id)],
            'target': 'current',
        }


class ProductSubTask(models.Model):
    _name = 'product.sub.task'
    _inherit = 'analytic.mixin'
    _rec_name = 'product_id'

    project_task_id = fields.Many2one("project.task", string=_("Project Task"))
    product_id = fields.Many2one("product.product", string=_("Product"))
    quantity = fields.Float(string=_("Quantity"))
    quantity_product = fields.Float(string=_("Quantity"))
    remaining = fields.Float(string=_("Remaining"), compute='_compute_remaining', store=True,
                             inverse='_inverse_quantity_finished')
    finished = fields.Float(string=_("Finished"))
    budget_amount = fields.Float(string='Budget Amount', compute='_compute_analytic_distribution', store=True)

    @api.depends('quantity', 'finished')
    def _compute_remaining(self):
        """ Compute the remaining quantity."""
        for rec in self:
            rec.remaining = rec.quantity - rec.finished

    def _inverse_quantity_finished(self):
        """ Inverse the quantity and finished."""
        for rec in self:
            rec.finished = rec.quantity - rec.remaining

    @api.depends('analytic_distribution')
    def _compute_analytic_distribution(self):
        """ Computes the budget amount based on analytic distribution. """
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


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    project_task_id = fields.Many2one("project.task", string=_("Project Task"))
