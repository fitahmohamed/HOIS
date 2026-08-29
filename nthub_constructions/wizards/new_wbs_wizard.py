from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError



class NewWbsWizard(models.TransientModel):
    _name = 'new.wbs.wizard'
    _description = 'New WBS Wizard'

    project_id = fields.Many2one('project.project', string=_('Project'), readonly=True)
    unit_type_id = fields.Many2one('project.unit.type', string=_('Unit Type'))

    def confirm(self):
        order_lines = []
        if not self.project_id.partner_id:
            raise UserError(_('Please select a customer.'))

        contract = self.env['owner.contract'].search([('project_id', '=', self.project_id.id), ('is_owner', '=', True)])
        if not contract.partner_id:
            raise UserError(_('Please select a customer.'))
        wbs_name = f'{self.project_id.name}-{self.project_id.partner_id.name}'
        if self.project_id.num_of_units:
            for floor in range(1, self.project_id.num_of_units + 1):
                unit_name = f'{self.unit_type_id.name}-{floor}'

                order_lines.append((0, 0, {
                    'name': unit_name,
                    'customer_id': contract.partner_id.id,
                    'project_id': contract.project_id.id,
                }))

            wbs_order = self.env['project.wbs'].create({
                'name': wbs_name,
                'customer_id': contract.partner_id.id,
                'project_id': contract.project_id.id,
                'date': fields.Datetime.now(),
                'project_wbs_builds_ids': order_lines
            })

            for order in wbs_order.project_wbs_builds_ids:
                for line in contract.owner_contract_line_ids:
                    job_cost_lines = [(0, 0, {
                        'date': job.date,
                        'flag': job.flag,
                        'product_id': job.product_id.id,
                        'description': job.description,
                        'analytic_distribution': job.analytic_distribution,
                        'uom_id': job.uom_id.id,
                        'qty':job.qty,
                        'unit_price': job.unit_price
                    }) for job in line.template_id.job_cost_line_ids]
                    job_labour_lines = [(0, 0, {
                        'date': job.date,
                        'flag': job.flag,
                        'product_id': job.product_id.id,
                        'description':job.description,
                        'analytic_distribution': job.analytic_distribution,
                        'uom_id': job.uom_id.id,
                        'qty':job.qty,
                        'unit_price': job.unit_price,
                    }) for job in line.template_id.job_labour_line_ids]
                    job_equipment_lines = [(0, 0, {
                        'date': job.date,
                        'flag': job.flag,
                        'product_id': job.product_id.id,
                        'description': job.description,
                        'analytic_distribution': job.analytic_distribution,
                        'uom_id': job.uom_id.id,
                        'qty':job.qty,
                        'unit_price': job.unit_price,
                    }) for job in line.template_id.job_equipment_line_ids]
                    job_expense_lines = [(0, 0, {
                        'date': job.date,
                        'flag': job.flag,
                        'product_id': job.product_id.id,
                        'description': job.description,
                        'analytic_distribution': job.analytic_distribution,
                        'uom_id': job.uom_id.id,
                        'qty': job.qty,
                        'unit_price': job.unit_price,
                    }) for job in line.template_id.job_expense_line_ids]
                    job_subcontractor_lines = [(0, 0, {
                        'date': job.date,
                        'flag': job.flag,
                        'product_id': job.product_id.id,
                        'description': job.description,
                        'analytic_distribution': job.analytic_distribution,
                        'uom_id': job.uom_id.id,
                        'qty': job.qty,
                        'unit_price': job.unit_price,
                    }) for job in line.template_id.job_subcontractor_line_ids]
                    build_line = self.env['project.wbs.builds.line'].create({
                        'item_id': line.item_id.id,
                        'name': order.name + ' / ' + line.item_id.name,
                        'uom_id': line.uom_id.id,
                        'qty': line.quantity / wbs_order.project_id.num_of_units if wbs_order.project_id.num_of_units > 0 else 0.0,
                        'unit_price': line.price_unit,
                    })
                    wbs_template = self.env['wbs.job.cost'].create({
                        'name': order.name+' / '+line.item_id.name+' -'+' Template',
                        'employee_id': line.template_id.employee_id.id,
                        'department_id': line.template_id.department_id.id,
                        'ref_id': build_line.id,
                        'job_cost_line_ids': job_cost_lines,
                        'job_labour_line_ids': job_labour_lines,
                        'job_equipment_line_ids': job_equipment_lines,  
                        'job_expense_line_ids': job_expense_lines,
                        'job_subcontractor_line_ids': job_subcontractor_lines,
                    })
                    build_line.template_id = wbs_template
                    order.update({'project_wbs_builds_line_ids': [(4, build_line.id)]})

            # wbs_order.project_wbs_builds_ids.update({'project_wbs_builds_line_ids': builds_lines})
            # for line in contract.owner_contract_line_ids:
            #     for rec in line.template_id:
            #         job_cost_lines = []
            #         job_labour_lines = []
            #         job_equipment_lines = []
            #         job_expense_lines = []
            #         job_subcontractor_lines = []
            #         for job in rec.job_cost_line_ids:
            #             job_cost_lines.append((0, 0, {
            #                 'date': job.date,
            #                 'product_id': job.product_id.id,
            #                 'description': job.description,
            #                 'unit_value': job.unit_value,
            #                 'uom_id': job.uom_id.id,
            #                 'qty': 1.0,
            #                 'unit_price': job.unit_price,
            #             }))
            #         for job in rec.job_labour_line_ids:
            #             job_labour_lines.append((0, 0, {
            #                 'date': job.date,
            #                 'product_id': job.product_id.id,
            #                 'description': job.description,
            #                 'unit_value': job.unit_value,
            #                 'uom_id': job.uom_id.id,
            #                 'qty': 1.0,
            #                 'unit_price': job.unit_price,
            #             }))
            #         for job in rec.job_equipment_line_ids:
            #             job_equipment_lines.append((0, 0, {
            #                 'date': job.date,
            #                 'product_id': job.product_id.id,
            #                 'description': job.description,
            #                 'unit_value': job.unit_value,
            #                 'uom_id': job.uom_id.id,
            #                 'qty': 1.0,
            #                 'unit_price': job.unit_price,
            #             }))
            #         for job in rec.job_expense_line_ids:
            #             job_expense_lines.append((0, 0, {
            #                 'date': job.date,
            #                 'product_id': job.product_id.id,
            #                 'description': job.description,
            #                 'unit_value': job.unit_value,
            #                 'uom_id': job.uom_id.id,
            #                 'qty': 1.0,
            #                 'unit_price': job.unit_price,
            #             }))
            #         for job in rec.job_subcontractor_line_ids:
            #             job_subcontractor_lines.append((0, 0, {
            #                 'date': job.date,
            #                 'product_id': job.product_id.id,
            #                 'description': job.description,
            #                 'unit_value': job.unit_value,
            #                 'uom_id': job.uom_id.id,
            #                 'qty': 1.0,
            #                 'unit_price': job.unit_price,
            #             }))
            #         # for order in wbs_order.project_wbs_builds_ids.project_wbs_builds_line_ids:
            #         wbs_template = self.env['wbs.job.cost'].create({
            #             'name': unit_name,
            #             'ref_id': line.id,
            #             'job_cost_line_ids': job_cost_lines,
            #             'job_labour_line_ids': job_labour_lines,
            #             'job_equipment_line_ids': job_equipment_lines,
            #             'job_expense_line_ids': job_expense_lines,
            #             'job_subcontractor_line_ids': job_subcontractor_lines,
            #         })
            #         print('job_cost_lines', job_cost_lines)
            #         for tem in wbs_template:
            #                 if order.id == tem.ref_id.id:
            #                     order.update({'template_id': tem.id})

            form_view_id = self.env.ref("nthub_constructions.project_wbs_view_form").id
            return {
                'type': 'ir.actions.act_window',
                'name': _('Wbs'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'project.wbs',
                'views': [(form_view_id, 'form')],
                'target': 'current',
                'domain': [('id', '=', wbs_order.id)],
                'res_id': wbs_order.id

            }
        else:
            raise ValidationError("please fill required fields.(Number Of Unit) In Project")
