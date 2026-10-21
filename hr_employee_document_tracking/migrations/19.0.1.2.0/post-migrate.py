from odoo import SUPERUSER_ID, api

PREFIXES = ("passport", "iqama", "license", "driver_card", "medical")


def migrate(cr, version):
    """Documents filled in before this version get their "initial" history line."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    domain = ["|"] * (len(PREFIXES) - 1) + [(f"{p}_expiry_date", "!=", False) for p in PREFIXES]
    for emp in env["hr.employee"].with_context(active_test=False).search(domain):
        emp._sync_initial_document_history(PREFIXES)
