# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    internal_serial = fields.Char(string=_('Internal Serial'), copy=False)
    requisition_project_id = fields.Many2one(
        related='custom_requisition_id.project_id',
        store=True,
        string=_('Project'),
    )
    requisition_project_wbs_id = fields.Many2one(
        related='custom_requisition_id.project_wbs_id',
        store=True,
        string=_('WBS'),
    )
    requisition_wbs_builds_id = fields.Many2one(
        related='custom_requisition_id.wbs_builds_id',
        store=True,
        string=_('Unit'),
    )
    requisition_task_id = fields.Many2one(
        related='custom_requisition_id.task_id',
        store=True,
        string=_('Task'),
    )


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    last_purchase_price = fields.Float(
        string=_('Last Purchase Price'),
        compute='_compute_last_purchase_price',
    )
    requisition_project_id = fields.Many2one(
        related='custom_requisition_line_id.requisition_id.project_id',
        store=True,
        string=_('Project'),
    )
    requisition_project_wbs_id = fields.Many2one(
        related='custom_requisition_line_id.project_wbs_id',
        store=True,
        string=_('WBS'),
    )
    requisition_wbs_builds_id = fields.Many2one(
        related='custom_requisition_line_id.wbs_builds_id',
        store=True,
        string=_('Unit'),
    )
    requisition_task_id = fields.Many2one(
        related='custom_requisition_line_id.task_id',
        store=True,
        string=_('Task'),
    )

    @api.depends('product_id', 'order_id.date_order')
    def _compute_last_purchase_price(self):
        PurchaseLine = self.env['purchase.order.line']
        for line in self:
            line.last_purchase_price = 0.0
            if not line.product_id:
                continue
            domain = [
                ('product_id', '=', line.product_id.id),
                ('state', '=', 'purchase'),
                ('display_type', '=', False),
            ]
            if line.id:
                domain.append(('id', '!=', line.id))
            previous_line = PurchaseLine.search(
                domain,
                order='date_approve desc, date_order desc, id desc',
                limit=1,
            )
            line.last_purchase_price = previous_line.price_unit if previous_line else 0.0
