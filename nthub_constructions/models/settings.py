# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class ResConfigSettingsInherit(models.TransientModel):
    _inherit = 'res.config.settings'

    customer_compilation_journal_account_id = fields.Many2one(comodel_name='account.journal',
                                                              string=_('Customer Compilation Journal'),
                                                              config_parameter='nthub_constructions.customer_compilation_journal_account_id')
    customer_compilation_request_account_id = fields.Many2one(comodel_name='account.account',
                                                              string=_('Customer Compilation Request'),
                                                              config_parameter='nthub_constructions.customer_compilation_request_account_id')

    vendor_delivery_journal_account_id = fields.Many2one(comodel_name='account.journal',
                                                         string=_('Vendor Delivery Journal'),
                                                         config_parameter='nthub_constructions.vendor_delivery_journal_account_id')
    vendor_delivery_request_account_id = fields.Many2one(comodel_name='account.account',
                                                         string=_('Vendor Delivery Request'),
                                                         config_parameter='nthub_constructions.vendor_delivery_request_account_id')

    source_location_id = fields.Many2one(comodel_name='stock.location', string=_('Source Location'),
                                         config_parameter='nthub_constructions.source_location_id')
    # picking_type_id = fields.Many2one(comodel_name='stock.picking.type', string=_('Operation Type'),
    #                                      config_parameter='nthub_constructions.picking_type_id')
