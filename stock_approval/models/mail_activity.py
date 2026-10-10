
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def action_open_document(self):
        self.ensure_one()

        _logger.warning(
            "SIA ACTIVITY CLICK: id=%s, model=%s, res_id=%s, summary=%s",
            self.id,
            self.res_model,
            self.res_id,
            self.summary,
        )

        if self.res_model == "stock.quant" and self.res_id:
            quant = self.env["stock.quant"].browse(self.res_id)

            _logger.warning(
                "SIA QUANT STATUS: quant_id=%s, exists=%s, status=%s",
                quant.id,
                quant.exists(),
                quant.sia_status if quant.exists() else "missing",
            )

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
