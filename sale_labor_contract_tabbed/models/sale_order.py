from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_total_service_cost_all_lines = fields.Monetary(
        string="Total Service Cost (All Lines)",
        currency_field="currency_id",
        compute="_compute_x_labor_totals",
        store=True,
    )
    x_total_gosi_all_lines = fields.Monetary(
        string="Total GOSI (All Lines)",
        currency_field="currency_id",
        compute="_compute_x_labor_totals",
        store=True,
    )

    @api.depends("order_line.x_total_service_cost", "order_line.x_gosi_amount", "order_line.x_is_labor_line")
    def _compute_x_labor_totals(self):
        for order in self:
            labor_lines = order.order_line.filtered("x_is_labor_line")
            order.x_total_service_cost_all_lines = sum(labor_lines.mapped("x_total_service_cost"))
            order.x_total_gosi_all_lines = sum(labor_lines.mapped("x_gosi_amount"))

    def action_recalculate_labor_costs(self):
        for order in self:
            labor_lines = order.order_line.filtered("x_is_labor_line")
            labor_lines._apply_labor_defaults(force=False)
            labor_lines._recompute_labor_fields()
        return True

    def action_confirm(self):
        self.action_recalculate_labor_costs()
        return super().action_confirm()
