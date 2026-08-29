from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    admin_purchase_price = fields.Float(
        string='Administration Purchase Price',
        help='Maximum/reference purchase price set by the administration.',
        company_dependent=True,
    )


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    admin_purchase_price = fields.Float(
        string='Administration Price',
        related='product_id.product_tmpl_id.admin_purchase_price',
        readonly=True,
    )
    purchase_price_difference = fields.Float(
        string='Difference',
        compute='_compute_purchase_price_difference',
        store=True,
    )

    @api.depends('price_unit', 'admin_purchase_price')
    def _compute_purchase_price_difference(self):
        for line in self:
            line.purchase_price_difference = line.price_unit - line.admin_purchase_price


class MaterialPurchaseRequisitionLine(models.Model):
    _inherit = 'material.purchase.requisition.line'

    admin_purchase_price = fields.Float(
        string='Administration Price',
        related='product_id.product_tmpl_id.admin_purchase_price',
        readonly=True,
    )
    actual_purchase_price = fields.Float(
        string='Actual Purchase Price',
        compute='_compute_purchase_prices',
    )
    purchase_price_difference = fields.Float(
        string='Difference',
        compute='_compute_purchase_prices',
    )

    def _compute_purchase_prices(self):
        PurchaseLine = self.env['purchase.order.line']
        for line in self:
            po_lines = PurchaseLine.search([
                ('custom_requisition_line_id', '=', line.id),
                ('order_id.state', '!=', 'cancel'),
            ])
            actual = sum(po_lines.mapped('price_unit')) / len(po_lines) if po_lines else 0.0
            line.actual_purchase_price = actual
            line.purchase_price_difference = actual - line.admin_purchase_price
