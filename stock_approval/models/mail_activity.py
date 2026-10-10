from odoo import _, models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def action_open_document(self):
        self.ensure_one()

        if (
            self.res_model == "stock.quant"
            and self.summary == "Stock Adjustment Approval Required"
        ):
            view = self.env.ref(
                "stock.view_stock_quant_tree_inventory_editable"
            )

            return {
                "type": "ir.actions.act_window",
                "name": _("Physical Inventory Approvals"),
                "res_model": "stock.quant",
                "view_mode": "list",
                "views": [(view.id, "list")],
                "domain": [("sia_status", "=", "awaiting")],
                "context": {"inventory_mode": True},
                "target": "current",
            }

        return super().action_open_document()