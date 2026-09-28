# -*- coding: utf-8 -*-
# Copyright (C) 2023-TODAY TechKhedut (<https://www.techkhedut.com>)
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo.http import request
from odoo import http


class PropertyBrochureDetailsController(http.Controller):
    """Property Brochure Details Controller"""

    @http.route(['/property-brochure/<string:brocher_access_token>'], type='http', auth="public",
                website=True)
    def property_brochure_detail(self, brocher_access_token):
        """Property detail view based on access_token"""
        if not brocher_access_token:
            return request.redirect('/')

        property_sudo = request.env['property.details'].sudo()
        property_data = property_sudo.search(
            [('stage', '!=', 'draft'), ('brocher_access_token', '=', brocher_access_token)])

        if not property_data:
            return request.redirect('/')

        report_color = property_sudo.get_report_color()

        values = {
            'property_id': property_data,
            'report_color': report_color,
        }
        return request.render('rental_management.rental_property_details', values)
