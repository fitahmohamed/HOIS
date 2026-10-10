from odoo import _, models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def action_open_document(self):
        self.ensure_one()

        if self.res_model == "stock.quant" and self.res_id:
            quant = self.env["stock.quant"].browse(self.res_id)

            if quant.exists() and quant.sia_status == "awaiting":
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
                    "context": {
                        **self.env.context,
                        "inventory_mode": True,
                    },
                    "target": "current",
                }

        return super().action_open_document()