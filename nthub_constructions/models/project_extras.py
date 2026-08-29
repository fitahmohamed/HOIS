# -*- coding: utf-8 -*-
'''This model contains the project tender lines that used in the project tender'''
from odoo import models, fields, api, _


class ProjectExtras(models.Model):
    _name = 'project.extras'
    _description = 'Project.extras'
    _rec_name = 'name'

    product_id = fields.Many2one('product.product', string=_('Product'), help='Extra Product'
                                 , domain="[('type', '=', 'service')]",)
    date = fields.Date(string=_('Date'), help='Date', required=True, default=fields.Date.today())
    name = fields.Char(string=_('Name'))
    description = fields.Char(string=_('Description'))
    cost = fields.Float(string=_('Cost'))
    attachment = fields.Binary(string=_('Attachment'))
    project_id = fields.Many2one('project.project', string=_('Project'), help='project', ondelete='cascade',)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """
        This function is called whenever the 'product_id' field is changed.
        It updates the 'name' and 'cost' fields based on the selected product.

        Parameters:
            self: The current recordset.

        Returns:
            None
        """
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.cost = rec.product_id.lst_price
            else:
                rec.name = ''
                rec.cost = 0
