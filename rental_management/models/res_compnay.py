# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ResCompany(models.Model):
    """ Company """
    _inherit = 'res.company'

    property_mail_template_title = fields.Char(string="Title")
    property_mail_template_description = fields.Text(string="Description")

    section_title = fields.Char(string="Section Title")

    property_mail_section_one_title = fields.Char(string="Section One Title")
    property_mail_section_two_title = fields.Char(string="Section Two Title")
    property_mail_section_three_title = fields.Char(string="Section Three Title")

    property_mail_section_one_description = fields.Text(string="Section One Description")
    property_mail_section_two_description = fields.Text(string="Section Two Description")
    property_mail_section_three_description = fields.Text(string="Section Three Description")

    sold_property_mail_template_title = fields.Char(string="Title ")

    mail_template_image = fields.Binary(string="Image")
    contract_mail_template_image = fields.Binary(string="Contract Mail Template Image")
    sold_property_mail_template_image = fields.Binary(string="Sold Property Mail Template Image")
