# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MaterialPurchaseRequisitionInherit(models.Model):
    _inherit = 'material.purchase.requisition'

    state = fields.Selection(selection_add=[
        ('inventory_check', 'Inventory Check'),
    ], ondelete={'inventory_check': 'set default'})
    project_id = fields.Many2one('project.project', string=_('Project'))
    project_wbs_id = fields.Many2one('project.wbs', string=_('WBS'))
    wbs_builds_id = fields.Many2one('project.wbs.builds', string=_('Unit'))
    task_id = fields.Many2one('project.task', string=_('Task'))

    @api.onchange('project_id')
    def onchange_project_id(self):
        res = super().onchange_project_id()
        self.project_wbs_id = False
        self.wbs_builds_id = False
        self.task_id = False
        return res

    @api.onchange('project_wbs_id')
    def _onchange_project_wbs_id(self):
        self.wbs_builds_id = False
        self.task_id = False

    @api.onchange('wbs_builds_id')
    def _onchange_wbs_builds_id(self):
        self.task_id = False

    @api.onchange('task_id')
    def _onchange_task_id(self):
        for rec in self:
            task = rec.task_id
            if not task:
                continue
            rec.project_id = task.project_id
            rec.project_wbs_id = task.project_wbs_id or task.parent_id.project_wbs_id
            rec.wbs_builds_id = task.wbs_builds_id or task.parent_id.wbs_builds_id

    @api.constrains('project_id', 'project_wbs_id', 'wbs_builds_id', 'task_id')
    def _check_wbs_tracking_consistency(self):
        for rec in self:
            if rec.project_wbs_id and rec.project_wbs_id.project_id != rec.project_id:
                raise UserError(_('The selected WBS must belong to the selected project.'))
            if rec.wbs_builds_id and rec.wbs_builds_id.project_wbs_id != rec.project_wbs_id:
                raise UserError(_('The selected unit must belong to the selected WBS.'))
            if rec.task_id:
                task_wbs = rec.task_id.project_wbs_id or rec.task_id.parent_id.project_wbs_id
                task_unit = rec.task_id.wbs_builds_id or rec.task_id.parent_id.wbs_builds_id
                if rec.task_id.project_id != rec.project_id:
                    raise UserError(_('The selected task must belong to the selected project.'))
                if rec.project_wbs_id and task_wbs != rec.project_wbs_id:
                    raise UserError(_('The selected task must belong to the selected WBS.'))
                if rec.wbs_builds_id and task_unit != rec.wbs_builds_id:
                    raise UserError(_('The selected task must belong to the selected unit.'))

    def action_inventory_check(self):
        for rec in self:
            if not rec.requisition_line_ids:
                raise UserError(_('Please create some requisition lines.'))
            if not rec.location_id:
                raise UserError(_('Please select a source location before inventory check.'))
            for line in rec.requisition_line_ids:
                line.inventory_checked_qty = rec._get_inventory_available_qty(line)
            rec.state = 'inventory_check'

    def action_inventory_approve(self):
        for rec in self:
            if rec.state != 'inventory_check':
                continue
            rec._split_inventory_checked_lines()
            rec.requisition_confirm()

    def _get_inventory_available_qty(self, line):
        self.ensure_one()
        if not line.product_id or line.product_id.type == 'service':
            return 0.0
        domain = [('product_id', '=', line.product_id.id), ('location_id.usage', '=', 'internal')]
        if self.location_id:
            domain.append(('location_id', '=', self.location_id.id))
        return min(line.qty, sum(self.env['stock.quant'].sudo().search(domain).mapped('quantity')))

    def _split_inventory_checked_lines(self):
        for rec in self:
            for line in rec.requisition_line_ids:
                if line.product_id.type == 'service':
                    continue

                available_qty = min(max(line.inventory_checked_qty, 0.0), line.qty)
                purchase_qty = line.qty - available_qty
                original_qty = line.original_qty or line.qty
                vendor_ids = line.partner_id.ids

                if not available_qty:
                    line.write({
                        'requisition_type': 'purchase',
                        'original_qty': original_qty,
                        'inventory_checked_qty': 0.0,
                    })
                    continue

                line.write({
                    'qty': available_qty,
                    'requisition_type': 'internal',
                    'partner_id': [(5, 0, 0)],
                    'original_qty': original_qty,
                    'inventory_checked_qty': available_qty,
                })

                if purchase_qty:
                    line.copy({
                        'qty': purchase_qty,
                        'requisition_type': 'purchase',
                        'partner_id': [(6, 0, vendor_ids)],
                        'original_qty': original_qty,
                        'inventory_checked_qty': 0.0,
                    })

    def request_stock(self):
        """Override: after creating PO, update task material finished qty."""
        res = super().request_stock()
        for rec in self:
            if rec.task_id:
                rec._update_task_finished_qty()
        return res

    def _update_task_finished_qty(self):
        """Update finished qty on task's product_sub_task_ids from this requisition."""
        if not self.task_id:
            return
        for line in self.requisition_line_ids:
            if not line.product_id:
                continue
            # Find matching material line on the task
            task_mat = self.task_id.product_sub_task_ids.filtered(
                lambda x: x.product_id.id == line.product_id.id)
            if task_mat:
                # Recalculate total requisitioned for this product across all confirmed reqs
                total_req = 0
                all_reqs = self.env['material.purchase.requisition'].search([
                    ('task_id', '=', self.task_id.id),
                    ('state', 'in', ('stock', 'receive')),
                ])
                for req in all_reqs:
                    for req_line in req.requisition_line_ids:
                        # بنحسب الشراء بس — الصرف المخزني حركة تانية على نفس
                        # الكمية ومينفعش يتحسب مرتين في المنفذ
                        if (req_line.product_id.id == line.product_id.id
                                and req_line.requisition_type == 'purchase'):
                            total_req += req_line.qty
                task_mat[0].write({'finished': total_req})
