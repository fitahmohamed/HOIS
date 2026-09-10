# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    analytic_distribution_export = fields.Char(
        string="Analytic Distribution Export",
        compute="_compute_analytic_distribution_export",
        store=True,
        compute_sudo=True,
    )

    @api.depends("analytic_distribution")
    def _compute_analytic_distribution_export(self):
        AnalyticAccount = self.env["account.analytic.account"]

        for line in self:
            result = []

            for key, percentage in (line.analytic_distribution or {}).items():
                account_ids = [
                    int(x)
                    for x in key.split(",")
                    if x.strip().isdigit()
                ]

                accounts = AnalyticAccount.browse(account_ids)

                for account in accounts:
                    result.append(
                        f"{account.name}: {percentage}%"
                    )

            line.analytic_distribution_export = " | ".join(result)