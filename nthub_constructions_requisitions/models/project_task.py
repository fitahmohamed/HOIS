# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectTaskRequisition(models.Model):
    _inherit = 'project.task'

    requisition_ids = fields.One2many(
        'material.purchase.requisition', 'task_id',
        string=_('Requisitions'))
    requisition_count = fields.Integer(
        compute='_compute_requisition_count')

    def _compute_requisition_count(self):
        for rec in self:
            rec.requisition_count = self.env['material.purchase.requisition'].search_count([
                ('task_id', '=', rec.id)])

    def _get_prev_requisitioned_qty(self, req_type=None):
        """Get {product_id: total_qty} already requisitioned for this task.

        req_type: لو اتحدد ('purchase' أو 'internal') بيحسب النوع ده بس —
        عشان عدّاد الشراء منفصل عن عدّاد الصرف المخزني."""
        prev = {}
        reqs = self.env['material.purchase.requisition'].search([
            ('task_id', '=', self.id),
            ('state', 'not in', ('cancel', 'reject')),
        ])
        for req in reqs:
            for line in req.requisition_line_ids:
                if req_type and line.requisition_type != req_type:
                    continue
                prev[line.product_id.id] = prev.get(line.product_id.id, 0) + line.qty
        return prev

    def _get_breakdown_data(self):
        """Get breakdown line data {product_id: {price, analytic, budget}} from wbs.job.cost."""
        data = {}
        template = self.template_wbs_builds_line_id
        if not template:
            return data
        # template is wbs.job.cost - get all material lines
        for line in template.job_cost_line_ids:
            if line.product_id:
                data[line.product_id.id] = {
                    'unit_price': line.unit_price,
                    'total_cost': line.total_cost,
                    'analytic_distribution': line.analytic_distribution or {},
                }
        return data

    def _get_task_budget_total(self):
        """Get total cost from breakdown (wbs.job.cost) for this task."""
        template = self.template_wbs_builds_line_id
        if template:
            return template.jobcost_total
        return 0.0

    def action_create_requisition(self):
        """زر: إنشاء طلب شراء من خامات المهمة."""
        return self._create_requisition('purchase')

    def action_create_issue_requisition(self):
        """زر: إنشاء أمر صرف مخزني من خامات المهمة (بعد ما اتشترت ودخلت المخزن).
        الأصناف الخدمية بتتستبعد تلقائياً لأنها مالهاش صرف."""
        return self._create_requisition('internal')

    def _create_requisition(self, req_type):
        """Create a requisition from task materials.
        req_type: 'purchase' (شراء) أو 'internal' (صرف مخزني) —
        لكل نوع عدّاد متبقي مستقل."""
        self.ensure_one()
        prev_req = self._get_prev_requisitioned_qty(req_type)
        breakdown_data = self._get_breakdown_data()
        task_budget = self._get_task_budget_total()

        # Default analytic: from first breakdown line or project
        default_analytic = {}
        for bd in breakdown_data.values():
            if bd.get('analytic_distribution'):
                default_analytic = bd['analytic_distribution']
                break
        if not default_analytic and self.project_id and self.project_id.analytic_account_id:
            default_analytic = {str(self.project_id.analytic_account_id.id): 100.0}

        lines = []
        for mat in self.product_sub_task_ids:
            if not mat.product_id:
                continue
            # الصنف الخدمي: شراء بس — مالوش صرف مخزني
            if req_type == 'internal' and mat.product_id.type == 'service':
                continue
            original_qty = mat.quantity
            already_req = prev_req.get(mat.product_id.id, 0)
            remaining = original_qty - already_req
            if remaining <= 0:
                continue

            bd = breakdown_data.get(mat.product_id.id, {})
            cost_price = bd.get('unit_price', mat.product_id.standard_price)
            analytic = bd.get('analytic_distribution', default_analytic)
            budget = bd.get('total_cost', 0)

            lines.append((0, 0, {
                'product_id': mat.product_id.id,
                'description': mat.product_id.name,
                'qty': remaining,
                'uom': mat.product_id.uom_id.id,
                'requisition_type': req_type,
                'original_qty': original_qty,
                'budget_amount': budget,
                'breakdown_price': cost_price,
            }))

        if not lines:
            raise UserError(
                _('No remaining materials to purchase on this task.')
                if req_type == 'purchase' else
                _('لا توجد كميات متبقية للصرف المخزني — كل الأصناف اتصرفت '
                  'أو كلها أصناف خدمية.'))

        employee = self.env['hr.employee'].search([
            ('user_id', '=', self.env.uid)], limit=1)

        vals = {
            'project_id': self.project_id.id,
            'project_wbs_id': (self.project_wbs_id or self.parent_id.project_wbs_id).id,
            'wbs_builds_id': (self.wbs_builds_id or self.parent_id.wbs_builds_id).id,
            'task_id': self.id,
            'employee_id': employee.id if employee else False,
            'department_id': employee.department_id.id if employee and employee.department_id else False,
            'analytic_distribution': default_analytic,
            'requisition_line_ids': lines,
        }

        requisition = self.env['material.purchase.requisition'].create(vals)
        return {
            'name': _('Purchase Requisition'),
            'view_mode': 'form',
            'res_model': 'material.purchase.requisition',
            'res_id': requisition.id,
            'type': 'ir.actions.act_window',
            'context': {'form_view_initial_mode': 'edit'},
            'target': 'current',
        }

    def action_open_requisitions(self):
        """Open requisitions linked to this task."""
        self.ensure_one()
        return {
            'name': _('Requisitions'),
            'view_mode': 'list,form',
            'res_model': 'material.purchase.requisition',
            'domain': [('task_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_task_id': self.id, 'default_project_id': self.project_id.id},
            'target': 'current',
        }
