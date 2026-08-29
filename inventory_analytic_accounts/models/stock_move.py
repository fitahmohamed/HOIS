# -*- coding: utf-8 -*-
from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string='Analytic Account', copy=False)


def generate_analytic_distribution(analytic_account_id):
    plan_id = analytic_account_id.plan_id.id
    analytic_distribution = {str(analytic_account_id.id) + ',' + str(plan_id): 100.0}
    return analytic_distribution


class StockMove(models.Model):
    _inherit = 'stock.move'
    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string='Analytic Account', copy=False)

    def _generate_valuation_lines_data(self, valuation_partner_id, qty, debit_value, credit_value, debit_account_id,
                                       credit_account_id, svl_id, description):
        res = super(StockMove, self)._generate_valuation_lines_data(
            valuation_partner_id, qty, debit_value, credit_value,
            debit_account_id, credit_account_id, svl_id, description
        )

        if self.picking_id.analytic_account_id:
            analytic_distribution = generate_analytic_distribution(self.picking_id.analytic_account_id)
        elif self.analytic_account_id:
            analytic_distribution = generate_analytic_distribution(self.analytic_account_id)
        else:
            analytic_distribution = False

        res['debit_line_vals']['analytic_distribution'] = analytic_distribution

        res['credit_line_vals']['analytic_distribution'] = analytic_distribution

        return res
