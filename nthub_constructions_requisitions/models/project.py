# -*- coding: utf-8 -*-
from datetime import date
from odoo import models, fields, api, _


class Project(models.Model):
    _inherit = 'project.project'


    requisitions_count = fields.Integer(string=_('Requisitions'), compute='get_requisitions_count')


    def get_requisitions_count(self):
        """
        Get requisitions count
        """
        for rec in self:
            rec.requisitions_count = self.env['material.purchase.requisition'].search_count([
                ('project_id', '=', rec.id)])

    def action_open_requisitions(self):
        """
        Open requisitions
        """
        return {
            'name': _('Purchase Requisitions'),
            'domain': [('project_id', '=', self.id)],
            'view_mode': 'list,form',
            'res_model': 'material.purchase.requisition',
            'type': 'ir.actions.act_window',
            'context': {'default_project_id': self.id},
            'target': 'current',
        }

    def create_purchase_requisition(self):
        """
        Create new requisition
        """
        return {
            'name': _('Create Requisition'),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'material.purchase.requisition',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'default_project_id': self.id},
        }