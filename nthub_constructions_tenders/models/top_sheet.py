# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class TopSheet(models.Model):
    """ Model representing a Top Sheet in the system, used for tracking Tender costs. """
    _name = 'top.sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Top Sheet'
    _rec_name = "project_id"

    project_id = fields.Many2one("project.project", string=_('Project'))
    total_tender_cost = fields.Float(related="offer_id.total_cost", string=_('Direct Cost'))
    indirect_cost_percentage = fields.Float(string=_('Indirect Cost Percentage'),
                                            compute='_compute_indirect_cost_percentage')
    total_indirect_cost = fields.Float(related="offer_id.total_extra_cost", string=_('Indirect Cost'), )
    sub_total = fields.Float(related="offer_id.offer_total", string=_('Total Cost'))
    offer_id = fields.Many2one("tender.offer", string=_('Offer'))

    @api.depends('total_tender_cost', 'total_indirect_cost')
    def _compute_indirect_cost_percentage(self):
        """
        Compute the indirect cost percentage
        """
        for record in self:
            if record.total_tender_cost != 0:
                record.indirect_cost_percentage = (record.total_indirect_cost / record.total_tender_cost)
            else:
                record.indirect_cost_percentage = 0.0
