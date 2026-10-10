from odoo import _, fields, models
from odoo.exceptions import UserError


class StockQuant(models.Model):
    _name = "stock.quant"
    _inherit = ["stock.quant", "mail.thread", "mail.activity.mixin"]

    sia_status = fields.Selection(
        selection=[
            ("new", "New"),
            ("awaiting", "Awaiting Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Adjustment Status",
        default="new",
        copy=False,
    )
    sia_reason = fields.Text(string="Reason", copy=False)

    def _sia_approver_group(self):
        return self.env.ref("stock_approval.group_stock_inventory_approver")

    def action_apply_inventory(self):
        approver_group = self._sia_approver_group()
        if self.env.user in approver_group.user_ids:
            return super().action_apply_inventory()

        to_submit = self.filtered(lambda q: q.inventory_diff_quantity)
        remaining = self - to_submit
        for quant in to_submit:
            quant.sia_status = "awaiting"
            quant._sia_notify_approvers(approver_group)
        if remaining:
            return super(StockQuant, remaining).action_apply_inventory()
        return True

    
    def _sia_notify_approvers(self, approver_group):
        self.ensure_one()
        activity_type = self.env.ref("mail.mail_activity_data_todo")

        for user in approver_group.user_ids:
            self.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=user.id,
                summary="Stock Adjustment Approval Required",
                note=_(
                    "%(product)s at %(location)s: counted %(counted)s "
                    "(on hand %(onhand)s, diff %(diff)s). "
                    "Reason: %(reason)s. Requested by %(requester)s."
                ) % {
                    "product": self.product_id.display_name,
                    "location": self.location_id.display_name,
                    "counted": self.inventory_quantity,
                    "onhand": self.quantity,
                    "diff": self.inventory_diff_quantity,
                    "reason": self.sia_reason or _("Not specified"),
                    "requester": self.env.user.name,
                },
            )


    def action_sia_open_approval_list(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Stock Adjustment Approvals"),
            "res_model": "stock.quant",
            "view_mode": "list",
            "views": [
                (
                    self.env.ref(
                        "stock.view_stock_quant_tree_inventory_editable"
                    ).id,
                    "list",
                ),
            ],
            "domain": [
                ("sia_status", "=", "awaiting"),
            ],
            "target": "current",
        }

    def _sia_close_activities(self, feedback):
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        activities = self.env["mail.activity"].search([
            ("res_model", "=", "stock.quant"),
            ("res_id", "in", self.ids),
            ("activity_type_id", "=", activity_type.id),
        ])
        activities.action_feedback(feedback=feedback)

    def action_sia_approve(self):
        approver_group = self._sia_approver_group()
        if self.env.user not in approver_group.user_ids:
            raise UserError(_("You are not allowed to approve stock adjustments."))
        to_approve = self.filtered(lambda q: q.sia_status == "awaiting")
        to_approve._sia_close_activities(_("Approved"))
        result = super(StockQuant, to_approve).action_apply_inventory()
        to_approve.sia_status = "approved"
        return result

    def action_sia_reject(self):
        approver_group = self._sia_approver_group()
        if self.env.user not in approver_group.user_ids:
            raise UserError(_("You are not allowed to reject stock adjustments."))
        to_reject = self.filtered(lambda q: q.sia_status == "awaiting")
        to_reject._sia_close_activities(_("Rejected"))
        for quant in to_reject:
            quant.inventory_quantity = quant.quantity
        to_reject.sia_status = "rejected"

    def action_sia_open_reason_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Adjustment Reason"),
            "res_model": "stock.quant.reason.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_quant_id": self.id,
                "default_reason": self.sia_reason,
            },
        }