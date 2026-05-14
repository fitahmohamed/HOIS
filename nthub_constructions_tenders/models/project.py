# -*- coding: utf-8 -*-
from datetime import date
from odoo import models, fields, api, _
from odoo.exceptions import  UserError


class Project(models.Model):
    _inherit = 'project.project'

    offer_count = fields.Integer(string=_('Offers'), compute='get_offer_count')
    num_of_units = fields.Integer(string=_('Number of Units'), required=True)
    is_tender = fields.Boolean(string=_("Is Tender"))
    approved_tender = fields.Boolean(string=_("Approved Tender"))
    tender_ids = fields.One2many('project.tender', 'project_id', string=_("Tender"), copy=False, ondelete='cascade',
                                 index=True, )
    total_tender_cost = fields.Float(string=_("Total Tender Cost"), store=True, compute='_compute_tender_total')
    total_extra_cost = fields.Float(string=_("Total Extra Cost"), store=True, compute='_compute_tender_total')
    total_cost = fields.Float(string=_("Total Cost"), store=True, compute='_compute_tender_total')
    tender_submission_date = fields.Date(string=_("Tender Submission Date"))
    notes_tender = fields.Text(string=_("Notes"))
    tender_responsible_id = fields.Many2one('hr.employee', string=_("Tender Responsible"),
                                            default=lambda self: self.env.user.employee_id)
    tender_creation_date = fields.Date(string=_("Tender Creation Date"), default=fields.Date.today())
    tender_approval_date = fields.Date(string=_('Tender Approval Date'))
    contract_count = fields.Integer(string=_('Contract'), compute='get_contract_count')

    @api.onchange('num_of_units')
    def _onchange_num_of_units(self):
        """
        Set the number of units to at least 1
        """
        if self.num_of_units < 1:
            # Set the value to at least 1
            self.num_of_units = 1

    def action_create_offer(self):
        """
        Create an offer for the project
        """
        self.state = 'tender'
        order_lines = []
        for rec in self:
            if  not rec.partner_id:
                raise UserError(_('Please select a customer.'))
            for line in rec.tender_ids:
                order_lines.append((0, 0, {
                    'item_id': line.item_id.id,
                    'name': line.description,
                    'uom_id': line.uom_id.id,
                    'template_id': line.template_id.id,
                    'qty': line.qty,
                    'unit_price': line.unit_price,
                }))
            offer_order = self.env['tender.offer'].create({
                'customer_id': rec.partner_id.id,
                'project_id': rec.id,
                'date': fields.Datetime.now(),
                'order_line_ids': order_lines
            })
            version_order = self.env['tender.offer.version'].create({
                'customer_id': rec.partner_id.id,
                'project_id': rec.id,
                'state': 'confirm',
                'tender_offer_id': offer_order.id,
                'date': fields.Datetime.now(),
                'version_line_ids': order_lines
            })
            offer_order.update({
                'version_id': version_order.id,
            })
            return {
                'name': _('Tender Offer'),
                'view_mode': 'form',
                'view_id': False,
                'view_type': 'form',
                'res_model': 'tender.offer',
                'res_id': offer_order.id,
                'type': 'ir.actions.act_window',
                'target': 'current',
            }
    def get_offer_count(self):
        """
        Get the number of offers for the project
        """
        offer = self.env['tender.offer'].search([('project_id', '=', self.id)])
        self.offer_count = len(offer)

    def action_open_offer(self):
        """
        Open the offer for the project
        """
        offer = self.env['tender.offer'].search([('project_id', '=', self.id)])
        return {
            'name': _('Offers'),
            'domain': [('project_id', '=', self.id)],
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tender.offer',
            'type': 'ir.actions.act_window',
            'res_id': offer.id,
        }

    def action_confirm_tender(self):
        """This method confirms the tender and updates the state of the project to 'contract'."""
        for project in self:
            if project.offer_count > 0 and project.state != 'contract':
                if not project.partner_id:
                    raise UserError(_('Please select a customer.'))
                for line in project.tender_ids:
                    if line.qty == 0:
                        raise UserError(_('Please enter quantity for %s.') % line.item_id.name)
                if project.date:
                    project.write({'state': 'contract'})
                    offer = self.env['tender.offer'].search([('project_id', '=', project.id)])
                    offer.ensure_one()
                    if offer.state != 'confirm':
                        for line in offer.order_line_ids:
                            if line.qty == 0:
                                raise UserError(_('Please enter quantity for %s in offer.') % line.item_id.name)
                        offer.write({'state': 'approved'})
                        offer.version_id.write({'state': 'confirm'})
                    project.approved_tender = True
                    project.tender_approval_date = fields.Datetime.now()
                    project.contract_date = fields.Datetime.now()
                    contract_model = self.env['owner.contract']
                    contract_lines = []
                    offer_lines = offer.order_line_ids.filtered(lambda line: line.extra_expenses == False)
                    # extra_expenses_line = offer.order_line_ids.filtered(lambda line: line.extra_expenses == True)
                    for line in offer_lines:
                        line_data = {
                            'item_id': line.item_id.id,
                            'description': line.name,
                            'uom_id': line.uom_id.id,
                            'quantity': line.qty,
                            'price_unit': line.unit_price,
                            'template_id': line.template_id.id,
                            'percentage': 0,
                            'amount': line.qty * line.unit_price,
                        }
                        contract_lines.append((0, 0, line_data))
                    contract_vals = {
                        'project_id': project.id,
                        'partner_id': project.partner_id.id,
                        'date': project.date_start,
                        'end_date': project.date,
                        # 'extra_expenses': extra_expenses_line.sub_total,
                        'received_date': date.today(),
                        'currency_id': project.currency_id.id,
                        'down_payment_percentage': offer.down_payment_percentage,
                        'down_payment': offer.down_payment,
                        'is_owner': True,
                        'state': 'draft',
                        'owner_contract_line_ids': contract_lines,
                    }
                    contract_model.create(contract_vals)
                else:
                    raise UserError(_("Please set the end date for the tender."))
            return True

    def action_open_contract(self):
        """Open the contract records related to the current project."""
        contracts = self.env['owner.contract'].search([('project_id', '=', self.id), ('is_owner', '=', True)])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contract',
            'res_model': 'owner.contract',
            'view_type': 'form',
            'view_mode': 'form',
            'domain': [('id', 'in', contracts.ids)],
            'res_id': contracts.ids[0],
            'target': 'current',
        }

    def get_contract_count(self):
        """Calculate and set the count of contracts associated with the project."""
        for rec in self:
            contracts = rec.env['owner.contract'].search([
                ('project_id', '=', rec.id), ('is_owner', '=', True)])
            rec.contract_count = len(contracts)


    @api.depends('tender_ids', 'project_extras_ids')
    def _compute_tender_total(self):
        """Compute the total cost of the tender"""
        for rec in self:
            rec.total_tender_cost = sum([(p.qty * p.unit_price) for p in rec.tender_ids])
            rec.total_extra_cost = sum([x.cost for x in rec.project_extras_ids])
            rec.total_cost = rec.total_tender_cost + rec.total_extra_cost

