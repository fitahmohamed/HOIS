from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    available_in_pos = fields.Boolean("Available in POS", default=False)

    @api.model
    def get_new_partner(self, config_id, domain, offset):
        domain = list(domain or [])
        domain.append(("available_in_pos", "=", True))
        return super().get_new_partner(config_id, domain, offset)

    def _load_pos_data_domain(self, data, config):
        domain = super()._load_pos_data_domain(data, config)
        # Only load contacts explicitly flagged for POS visibility.
        domain.append(("available_in_pos", "=", True))
        return domain
