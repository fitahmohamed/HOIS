# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    analytic_distribution_export = fields.Char(
        string="Analytic Distribution",
        compute="_compute_analytic_distribution_export",
        store=True,
    )

    @api.depends("analytic_distribution")
    def _compute_analytic_distribution_export(self):
        for line in self:
            result = []

            if line.analytic_distribution:
                for analytic_accounts, percentage in line.analytic_distribution.items():
                    # analytic_accounts may contain multiple analytic account IDs
                    account_ids = [
                        int(account_id)
                        for account_id in analytic_accounts.split(",")
                        if account_id
                    ]

                    accounts = self.env["account.analytic.account"].browse(account_ids)

                    account_names = ", ".join(accounts.mapped("name"))

                    result.append(
                        f"{account_names}: {percentage}%"
                    )

            line.analytic_distribution_export = " | ".join(result)
