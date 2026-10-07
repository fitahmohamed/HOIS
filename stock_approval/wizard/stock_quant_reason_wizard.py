from odoo import fields, models


class StockQuantReasonWizard(models.TransientModel):
    _name = "stock.quant.reason.wizard"
    _description = "Stock Quant Adjustment Reason"

    quant_id = fields.Many2one("stock.quant", required=True)
    reason = fields.Text(string="Reason")

    def action_save(self):
        self.ensure_one()
        self.quant_id.sia_reason = self.reason
        return {"type": "ir.actions.act_window_close"}