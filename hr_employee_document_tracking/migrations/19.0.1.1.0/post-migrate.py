from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Status fields became automatic: recompute them from the expiry dates."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["hr.employee"]._recompute_document_status()
