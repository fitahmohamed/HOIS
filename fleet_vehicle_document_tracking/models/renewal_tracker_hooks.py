from odoo import api, models

STATUS_SETTINGS = {"critical_days", "warning_days"}


class RenewalDocument(models.Model):
    _inherit = "renewal.document"

    @api.model
    def _cron_check_renewals(self):
        """The daily renewal_tracker cron also handles vehicle documents."""
        res = super()._cron_check_renewals()
        self.env["fleet.vehicle"]._cron_vehicle_document_alerts()
        return res


class RenewalSettings(models.Model):
    _inherit = "renewal.settings"

    def write(self, vals):
        res = super().write(vals)
        if STATUS_SETTINGS & set(vals):
            self.env["fleet.vehicle"]._recompute_document_status()
        return res
