from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockQuant(models.Model):
    _name = "stock.quant"
    _inherit = ["stock.quant", "mail.thread", "mail.activity.mixin"]

    saa_status = fields.Selection(
        selection=[("new", "New"), ("awaiting", "Awaiting Approval")],
        string="Adjustment Status",
        default="new",
        copy=False,
    )

    def _saa_approver_group(self):
        return self.env.ref("stock_adjustment_approval.group_stock_adjustment_approver")

    def action_apply_inventory(self):
        approver_group = self._saa_approver_group()
        if self.env.user in approver_group.users:
            return super().action_apply_inventory()

        to_submit = self.filtered(lambda q: q.inventory_diff_quantity)
        remaining = self - to_submit
        for quant in to_submit:
            quant.saa_status = "awaiting"
            quant._saa_notify_approvers(approver_group)
        if remaining:
            return super(StockQuant, remaining).action_apply_inventory()
        return True

    def _saa_notify_approvers(self, approver_group):
        self.ensure_one()
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        for user in approver_group.users:
            self.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=user.id,
                summary=_("Stock Adjustment Approval Required"),
                note=_(
                    "%(product)s at %(location)s: counted %(counted)s (on hand %(onhand)s, diff %(diff)s) requested by %(requester)s."
                ) % {
                    "product": self.product_id.display_name,
                    "location": self.location_id.display_name,
                    "counted": self.inventory_quantity,
                    "onhand": self.quantity,
                    "diff": self.inventory_diff_quantity,
                    "requester": self.env.user.name,
                },
            )

    def _saa_close_activities(self, feedback):
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        activities = self.env["mail.activity"].search([
            ("res_model", "=", "stock.quant"),
            ("res_id", "in", self.ids),
            ("activity_type_id", "=", activity_type.id),
        ])
        activities.action_feedback(feedback=feedback)

    def action_saa_approve(self):
        approver_group = self._saa_approver_group()
        if self.env.user not in approver_group.users:
            raise UserError(_("You are not allowed to approve stock adjustments."))
        to_approve = self.filtered(lambda q: q.saa_status == "awaiting")
        to_approve._saa_close_activities(_("Approved"))
        result = super(StockQuant, to_approve).action_apply_inventory()
        to_approve.saa_status = "new"
        return result

    def action_saa_reject(self):
        approver_group = self._saa_approver_group()
        if self.env.user not in approver_group.users:
            raise UserError(_("You are not allowed to reject stock adjustments."))
        to_reject = self.filtered(lambda q: q.saa_status == "awaiting")
        to_reject._saa_close_activities(_("Rejected"))
        for quant in to_reject:
            quant.inventory_quantity = quant.quantity
        to_reject.saa_status = "new"