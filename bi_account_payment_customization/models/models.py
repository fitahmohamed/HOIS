# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_log = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = 'res.currency'
    arabic_name = fields.Char()
    arabic_cents_name = fields.Char("Cent Arabic name")


class ResCountry(models.Model):
    _inherit = 'res.country'
    arabic_name = fields.Char('Credit Days')


class ResCompany(models.Model):
    _inherit = 'res.company'

    arabic_name = fields.Char('Name in Arabic')
    arabic_street = fields.Char('Arabic Street')
    arabic_street2 = fields.Char('Arabic Street2')
    arabic_city = fields.Char('Arabic City')
    arabic_state_id = fields.Char('Arabic State')
    arabic_country_id = fields.Char('Arabic Country', related="country_id.arabic_name", store=True, readonly=False)
