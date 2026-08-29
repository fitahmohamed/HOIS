# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MaterialPurchaseRequisitionLineInherit(models.Model):
    _inherit = 'material.purchase.requisition.line'

    original_qty = fields.Float(string=_('Original Qty'), readonly=True)
    # الكميات السابقة بتتحسب لكل نوع لوحده:
    # الشراء له عدّاد والصرف المخزني له عدّاد — عشان شراء 100 ما يمنعش صرف الـ100
    prev_requisitioned_qty = fields.Float(
        string=_('Prev. (Same Type)'),
        compute='_compute_prev_requisitioned_qty',
        help='إجمالي الكميات المطلوبة سابقاً لنفس الصنف على نفس المهمة '
             'ولنفس النوع (شراء مع شراء / صرف مع صرف).')
    remaining_qty = fields.Float(string=_('Remaining'), compute='_compute_remaining_qty')
    budget_amount = fields.Float(string=_('Budget'), readonly=True)
    breakdown_price = fields.Float(string=_('Breakdown Price'), readonly=True)
    line_total = fields.Float(string=_('Estimated Cost'), compute='_compute_line_total')
    inventory_checked_qty = fields.Float(string=_('Inventory Checked Qty'))
    project_wbs_id = fields.Many2one(
        related='requisition_id.project_wbs_id',
        store=True,
        string=_('WBS'),
    )
    wbs_builds_id = fields.Many2one(
        related='requisition_id.wbs_builds_id',
        store=True,
        string=_('Unit'),
    )
    task_id = fields.Many2one(
        related='requisition_id.task_id',
        store=True,
        string=_('Task'),
    )

    @api.depends('product_id', 'requisition_type',
                 'requisition_id.task_id', 'requisition_id.state')
    def _compute_prev_requisitioned_qty(self):
        for rec in self:
            task = rec.requisition_id.task_id
            if not task or not rec.product_id:
                rec.prev_requisitioned_qty = 0.0
                continue
            origin_req_id = rec.requisition_id._origin.id
            domain = [
                ('requisition_id.task_id', '=', task.id),
                ('product_id', '=', rec.product_id.id),
                ('requisition_type', '=', rec.requisition_type),
                ('requisition_id.state', 'not in', ('cancel', 'reject')),
            ]
            if origin_req_id:
                domain.append(('requisition_id', '!=', origin_req_id))
            rec.prev_requisitioned_qty = sum(self.search(domain).mapped('qty'))

    @api.depends('original_qty', 'prev_requisitioned_qty', 'qty')
    def _compute_remaining_qty(self):
        for rec in self:
            rec.remaining_qty = rec.original_qty - rec.prev_requisitioned_qty - rec.qty

    @api.depends('qty', 'breakdown_price')
    def _compute_line_total(self):
        for rec in self:
            rec.line_total = rec.qty * rec.breakdown_price

    @api.onchange('product_id', 'requisition_type')
    def _onchange_service_no_internal(self):
        """الصنف الخدمي مالوش صرف مخزني — يتحول شراء تلقائياً."""
        for rec in self:
            if (rec.product_id and rec.product_id.type == 'service'
                    and rec.requisition_type == 'internal'):
                rec.requisition_type = 'purchase'
                return {'warning': {
                    'title': _('Service Product'),
                    'message': _('الصنف "%s" خدمي — مش محتاج صرف مخزني، '
                                 'تم تحويل النوع لشراء.') % rec.product_id.name,
                }}

    @api.constrains('requisition_type', 'product_id')
    def _check_service_no_internal(self):
        for rec in self:
            if (rec.requisition_type == 'internal'
                    and rec.product_id.type == 'service'):
                raise UserError(_(
                    'الصنف "%s" خدمي ولا يمكن عمل صرف مخزني له — '
                    'استخدم نوع "شراء".') % rec.product_id.name)

    @api.constrains('qty', 'requisition_type')
    def _check_qty_not_exceed(self):
        """السقف بيتحسب لكل نوع لوحده:
        - الشراء: إجمالي المشتري <= كمية البند الأصلية
        - الصرف: إجمالي المصروف <= كمية البند الأصلية
        فبعد شراء الـ100 تقدر عادي تعمل أمر صرف للـ100."""
        for rec in self:
            if not rec.original_qty:
                continue
            max_allowed = rec.original_qty - rec.prev_requisitioned_qty
            if rec.qty > max_allowed:
                if not self.env.user.has_group(
                        'nthub_constructions_tenders.construction_requisition_over_budget'):
                    type_label = (_('شراء') if rec.requisition_type == 'purchase'
                                  else _('صرف مخزني'))
                    raise UserError(_(
                        'الكمية %.2f للصنف "%s" تتجاوز المتبقي المسموح (%.2f) '
                        'لنوع "%s". تحتاج صلاحية "Allow Over-Budget Requisition".'
                    ) % (rec.qty, rec.product_id.name, max_allowed, type_label))
