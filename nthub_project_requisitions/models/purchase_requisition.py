# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date
from odoo.exceptions import UserError


class MaterialPurchaseRequisition(models.Model):
    _name = 'material.purchase.requisition'
    _description = 'Purchase Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'

    # region ---------------------- TODO[IMP]:Default Methods ------------------------------------
    def _default_transit_location(self):
        """
        :return: default transit location
        """
        return self.env['stock.location'].search(
            [('usage', '=', 'internal'),
             ('warehouse_id', '=', self.env.ref('nthub_project_requisitions.con_transit_warehouse').id)],
            limit=1)

    def _default_transit_picking_type(self):
        """
        :return: default transit picking type
        """
        return self.env['stock.picking.type'].search([('code', '=', 'internal'), (
        'warehouse_id', '=', self.env.ref('nthub_project_requisitions.con_transit_warehouse').id)], limit=1)

    # endregion

    # region ---------------------- TODO[IMP]: Fields Declaration ---------------------------------
    # region  Basic
    name = fields.Char(string='Number', index=True, readonly=1, )
    request_date = fields.Date(string='Requisition Date', default=fields.Date.today(), required=True)
    date_end = fields.Date(string='Requisition Deadline', readonly=True, help='Last date for the product to be needed',
                           copy=True)
    date_done = fields.Date(string='Date Done', readonly=True, help='Date of Completion of Purchase Requisition')
    managerapp_date = fields.Date(string='Department Approval Date', readonly=True, copy=False)
    manareject_date = fields.Date(string='Department Manager Reject Date', readonly=True)
    userreject_date = fields.Date(string='Rejected Date', readonly=True, copy=False)
    userrapp_date = fields.Date(string='Approved Date', readonly=True, copy=False)
    receive_date = fields.Date(string='Received Date', readonly=True, copy=False)
    reason = fields.Text(string='Reason for Requisitions', required=False, copy=True)
    confirm_date = fields.Date(string='Confirmed Date', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'New'),
        ('dept_confirm', 'Waiting Department Approval'),
        ('ir_approve', 'Waiting IR Approval'),
        ('approve', 'Approved'),
        ('stock', 'Purchase Order Created'),
        ('receive', 'Received'),
        ('cancel', 'Cancelled'),
        ('reject', 'Rejected')],
        default='draft',
        track_visibility='onchange',
    )

    transfer_type = fields.Selection(
        [('internal_company', 'Internal Company'), ('between_companies', 'Between Companies')],
        compute='_compute_transfer_type')

    analytic_distribution = fields.Json('Analytic Distribution', )
    # endregion

    # region  Relational
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        copy=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1),
        required=True,
        copy=True,
    )
    source_employee_id = fields.Many2one(
        'hr.employee',
        copy=True,
    )
    approve_manager_id = fields.Many2one(
        'hr.employee',
        string='Department Manager',
        readonly=True,
        copy=False,
    )
    reject_manager_id = fields.Many2one(
        'hr.employee',
        string='Department Manager Reject',
        readonly=True,
    )
    approve_employee_id = fields.Many2one(
        'hr.employee',
        string='Approved by',
        readonly=True,
        copy=False,
    )
    reject_employee_id = fields.Many2one(
        'hr.employee',
        string='Rejected by',
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.user.company_id,
        required=True,
        copy=True,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        copy=True,
    )
    requisition_line_ids = fields.One2many(
        'material.purchase.requisition.line',
        'requisition_id',
        string='Purchase Requisitions Line',
        copy=True,
    )

    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env['decimal.precision'].precision_get("Percentage Analytic"),
    )

    dest_location_id = fields.Many2one(  # required
        'stock.location',
        string='Destination Location',
        required=False,
        copy=True,
    )
    # delivery_picking_id = fields.Many2one(
    #     'stock.picking',
    #     string='Internal Picking',
    #     readonly=True,
    #     copy=False,
    # )
    requisition_responsible_id = fields.Many2one(
        'hr.employee',
        string='Requisition Responsible',
        copy=True,
    )
    employee_confirm_id = fields.Many2one(
        'hr.employee',
        string='Confirmed by',
        readonly=True,
        copy=False,
    )

    purchase_order_ids = fields.One2many(
        'purchase.order',
        'custom_requisition_id',
        string='Purchase Orders',
    )
    custom_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Picking Type',
        copy=False,
    )

    # FIXme Add Transit location in Requisition
    transit_location_id = fields.Many2one('stock.location', string=_('Transit Location'), copy=True, )
    custom_picking_trans_type_id = fields.Many2one('stock.picking.type', string=_('Picking Transit Type'))

    project_id = fields.Many2one('project.project', string=_('Project'))
    source_debit_account_id = fields.Many2one('account.account', string=_('Source Debit Account'))

    destination_credit_account_id = fields.Many2one('account.account',
                                                    string=_('Destination Credit Account'))  # required

    source_journal_id = fields.Many2one('account.journal', string=_('Source Journal'))

    destination_journal_id = fields.Many2one('account.journal', string=_('Destination Journal'))  # required
    # endregion

    # region  Computed
    picking_counter = fields.Integer(string='Picking Counter', compute="_compute_picking_counter")
    po_counter = fields.Integer(string='Picking Counter', compute="_compute_po_counter")

    # endregion

    # region ---------------------- TODO[IMP]: Compute methods ------------------------------------
    @api.depends('location_id', 'dest_location_id')
    def _compute_transfer_type(self):
        for rec in self:
            if rec.location_id and rec.dest_location_id:
                if rec.location_id.company_id == rec.dest_location_id.company_id:
                    rec.transfer_type = 'internal_company'
                else:
                    rec.transfer_type = 'between_companies'
            else:
                rec.transfer_type = False

    def _compute_picking_counter(self):
        """
        compute picking counter
        """
        for rec in self:
            rec.picking_counter = self.env['stock.picking'].search_count([('custom_requisition_id', '=', rec.id)])

    def _compute_po_counter(self):
        """
        compute picking counter
        """
        for rec in self:
            rec.po_counter = self.env['purchase.order'].search_count([('custom_requisition_id', '=', rec.id)])

    # endregion

    # region ---------------------- TODO[IMP]: Constrains and Onchanges ---------------------------
    @api.onchange('project_id')
    def onchange_project_id(self):
        """
        onchange project id
        """
        if self.project_id:
            location_ids = self.env['stock.location'].search(
                [('usage', '=', 'internal'), ('warehouse_id', '=', self.project_id.warehouse_id.id)]).ids
            if location_ids:
                self.dest_location_id = location_ids[0]
                return {'domain': {'dest_location_id': [('id', 'in', location_ids)]}}

    # @api.onchange('location_id')
    # def onchange_location_id(self):
    #     """
    #     onchange location id
    #     """
    #     if self.transfer_type == 'internal_company':
    #         if self.location_id:
    #             self.custom_picking_type_id = self.env['stock.picking.type'].search(
    #                 [('code', '=', 'internal'), ('warehouse_id', '=', self.location_id.warehouse_id.id)], limit=1)

    @api.onchange('employee_id')
    def set_department(self):
        """
        set department
        """
        for rec in self:
            rec.department_id = rec.employee_id.sudo().department_id.id
            rec.dest_location_id = rec.employee_id.sudo().dest_location_id.id or rec.employee_id.sudo().department_id.dest_location_id.id

    # endregion

    # region ---------------------- TODO[IMP]: CRUD Methods ---------------------------------------
    def unlink(self):
        """
        Delete the current record if its state is 'draft'.
        :return: bool
            Returns True if the record is successfully deleted, otherwise raises an exception.
        """
        for rec in self:
            if rec.state not in ('draft', 'cancel', 'reject'):
                raise UserError(
                    _('You can not delete Purchase Requisition which is not in draft or cancelled or rejected state.'))
        return super(MaterialPurchaseRequisition, self).unlink()

    @api.model
    def create(self, vals_list):
        """
        Create a new 'MaterialPurchaseRequisition' record with a unique name.
        """
        for vals in vals_list:  
            name = self.env['ir.sequence'].next_by_code('purchase.requisition.seq')
            vals.update({
                'name': name
            })
        res = super(MaterialPurchaseRequisition, self).create(vals_list)
        return res

    # endregion

    # region ---------------------- TODO[IMP]: Action Methods -------------------------------------
    def requisition_confirm(self):
        """
        confirm requisition
        """
        for rec in self:
            manager_mail_template = self.env.ref(
                'nthub_project_requisitions.email_confirm_material_purchase_requistion')
            rec.employee_confirm_id = rec.employee_id.id
            rec.confirm_date = fields.Date.today()
            rec.state = 'dept_confirm'
            if manager_mail_template:
                manager_mail_template.send_mail(self.id)

    def requisition_reject(self):
        """
        reject requisition
        """
        for rec in self:
            rec.state = 'reject'
            rec.reject_employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            rec.userreject_date = fields.Date.today()

    def manager_approve(self):
        """
        manager approve
        """
        for rec in self:
            rec.managerapp_date = fields.Date.today()
            rec.approve_manager_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            employee_mail_template = self.env.ref('nthub_project_requisitions.email_purchase_requisition_iruser_custom')
            email_iruser_template = self.env.ref('nthub_project_requisitions.email_purchase_requisition')
            employee_mail_template.sudo().send_mail(self.id)
            email_iruser_template.sudo().send_mail(self.id)
            rec.state = 'ir_approve'

    def user_approve(self):
        """
        user approve
        """
        for rec in self:
            rec.userrapp_date = fields.Date.today()
            rec.approve_employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            rec.state = 'approve'

    def reset_draft(self):
        """
        reset to draft
        """
        for rec in self:
            rec.state = 'draft'

    def request_stock(self):
        """
        request stock
        """
        stock_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        # internal_obj = self.env['stock.picking.type'].search([('code','=', 'internal')], limit=1)
        # internal_obj = self.env['stock.location'].search([('usage','=', 'internal')], limit=1)
        purchase_obj = self.env['purchase.order']
        purchase_line_obj = self.env['purchase.order.line']
        #         if not internal_obj:
        #             raise UserError(_('Please Specified Internal Picking Type.'))
        for rec in self:
            if not rec.requisition_line_ids:
                raise UserError(_('Please create some requisition lines.'))
            # TODo: Internal Picking
            if any(line.requisition_type == 'internal' for line in rec.requisition_line_ids):
                if not rec.location_id.id:
                    raise UserError(_('Select Source location under the picking details.'))
                if not rec.custom_picking_type_id.id:
                    raise UserError(_('Select Picking Type under the picking details.'))
                if not rec.dest_location_id:
                    raise UserError(_('Select Destination location under the picking details.'))
                if not rec.transit_location_id:
                    raise UserError(_('Select Transited location under the picking details.'))
                if not rec.custom_picking_trans_type_id.id:
                    raise UserError(_('Select Transited Picking Type under the picking details.'))
                if not rec.source_employee_id and rec.transfer_type == 'between_companies':
                    raise UserError(_('Please Select Source Employee Responsible.'))

                #                 if not rec.employee_id.dest_location_id.id or not rec.employee_id.department_id.dest_location_id.id:
                #                     raise Warning(_('Select Destination location under the picking details.'))
                self.generate_source_picking()
                self.generate_destination_picking()
            po_dict = {}
            for line in rec.requisition_line_ids:
                if line.requisition_type == 'purchase':  # 10/12/2019
                    if not line.partner_id:
                        raise UserError(
                            _('Please enter atleast one vendor on Requisition Lines for Requisition Action Purchase'))
                    #                        raise Warning(_('Please enter atleast one vendor on Requisition Lines for Requisition Action Purchase'))
                    for partner in line.partner_id:
                        if partner not in po_dict:
                            po_vals = {
                                'partner_id': partner.id,
                                'currency_id': rec.env.user.company_id.currency_id.id,
                                'date_order': fields.Date.today(),
                                #                                'company_id':rec.env.user.company_id.id,
                                'company_id': rec.company_id.id,
                                'custom_requisition_id': rec.id,
                                'origin': rec.name,
                            }
                            purchase_order = purchase_obj.create(po_vals)
                            po_dict.update({partner: purchase_order})
                            po_line_vals = rec._prepare_po_line(line, purchase_order)
                            #                            {
                            #                                     'product_id': line.product_id.id,
                            #                                     'name':line.product_id.name,
                            #                                     'product_qty': line.qty,
                            #                                     'product_uom': line.uom.id,
                            #                                     'date_planned': fields.Date.today(),
                            #                                     'price_unit': line.product_id.lst_price,
                            #                                     'order_id': purchase_order.id,
                            #                                     'account_analytic_id': rec.analytic_account_id.id,
                            #                            }
                            purchase_line_obj.sudo().create(po_line_vals)
                        else:
                            purchase_order = po_dict.get(partner)
                            po_line_vals = rec._prepare_po_line(line, purchase_order)
                            #                            po_line_vals =  {
                            #                                 'product_id': line.product_id.id,
                            #                                 'name':line.product_id.name,
                            #                                 'product_qty': line.qty,
                            #                                 'product_uom': line.uom.id,
                            #                                 'date_planned': fields.Date.today(),
                            #                                 'price_unit': line.product_id.lst_price,
                            #                                 'order_id': purchase_order.id,
                            #                                 'account_analytic_id': rec.analytic_account_id.id,
                            #                            }
                            purchase_line_obj.sudo().create(po_line_vals)
                rec.state = 'stock'

    def action_received(self):
        """
        received
        """
        for rec in self:
            rec.receive_date = fields.Date.today()
            rec.state = 'receive'

    def action_cancel(self):
        """
        cancel
        """
        for rec in self:
            rec.state = 'cancel'

    def show_picking(self):
        """
        show picking
        """
        for rec in self:
            res = self.sudo().env.ref('stock.action_picking_tree_all')
            res = res.read()[0]
            res['domain'] = str([('custom_requisition_id', '=', rec.id)])
        return res

    def action_show_po(self):
        """
            Action to show purchase orders related to the current custom requisition."""
        for rec in self:
            purchase_action = self.env.ref('purchase.purchase_rfq')
            purchase_action = purchase_action.read()[0]
            purchase_action['domain'] = str([('custom_requisition_id', '=', rec.id)])
        return purchase_action

    # endregion

    # region ---------------------- TODO[IMP]: Business Methods -----------------------------------
    @api.model
    def _prepare_source_pick_vals(self, line=False, stock_id=False):
        """
        prepare picking vals
        """
        pick_vals = {
            'product_id': line.product_id.id,
            'product_uom_qty': line.qty,
            'product_uom': line.uom.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.transit_location_id.id,
            # 'name': line.product_id.name,
            'picking_type_id': self.custom_picking_type_id.id,
            'picking_id': stock_id.id,
            'custom_requisition_line_id': line.id,
            'company_id': self.location_id.company_id.id,
        }
        return pick_vals

    @api.model
    def _prepare_dest_pick_vals(self, line=False, stock_id=False):
        """
        prepare picking vals
        """
        pick_vals = {
            'product_id': line.product_id.id,
            'product_uom_qty': line.qty,
            'product_uom': line.uom.id,
            'location_id': self.transit_location_id.id,
            'location_dest_id': self.dest_location_id.id,
            # 'name': line.product_id.name,
            'picking_type_id': self.custom_picking_trans_type_id.id,
            'picking_id': stock_id.id,
            'custom_requisition_line_id': line.id,
            'company_id': self.dest_location_id.company_id.id,
        }
        return pick_vals

    @api.model
    def _prepare_po_line(self, line=False, purchase_order=False):
        """
        prepare purchase order line vals
        """
        po_line_vals = {
            'product_id': line.product_id.id,
            'name': line.product_id.name,
            'product_qty': line.qty,
            'product_uom': line.uom.id,
            'date_planned': fields.Date.today(),
            'price_unit': line.product_id.standard_price,
            'order_id': purchase_order.id,
            'analytic_distribution': self.analytic_distribution,
            # 'account_analytic_id': self.analytic_account_id.id,
            'custom_requisition_line_id': line.id
        }
        return po_line_vals

    def generate_source_picking(self):
        """
        generate source picking
        """
        picking_vals = {
            'partner_id': self.source_employee_id.sudo().work_contact_id.id if self.transfer_type == 'between_companies' else self.employee_id.sudo().address_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.transit_location_id and self.transit_location_id.id,
            'picking_type_id': self.custom_picking_type_id.id,  # internal_obj.id,
            'note': self.reason,
            'custom_requisition_id': self.id,
            'origin': self.name,
        }
        stock_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        stock_id = stock_obj.sudo().create(picking_vals)
        lines = []
        for line in self.requisition_line_ids:
            if line.requisition_type == 'internal':
                pick_vals = self._prepare_source_pick_vals(line, stock_id)
                move_id = move_obj.sudo().create(pick_vals)
                if (self.transfer_type == 'between_companies' and self.source_debit_account_id
                        and self.destination_credit_account_id):
                    lines.append((0, 0, {
                        'account_id': line.product_id.categ_id.with_company(
                            self.location_id.company_id).property_stock_valuation_account_id.id,
                        'credit': line.with_company(self.location_id.company_id).product_id.standard_price * line.qty,
                        'name': line.product_id.name,
                        'debit': 0.0,
                    }))
            if (self.transfer_type == 'between_companies' and self.source_debit_account_id
                    and self.destination_credit_account_id):
                lines.append((0, 0, {
                    'account_id': self.source_debit_account_id.id,
                    'debit': sum(
                        [product.with_company(self.location_id.company_id).product_id.standard_price * product.qty for
                         product in self.requisition_line_ids]),
                    'credit': 0.0,
                    'display_type': 'product',
                }))
                source_journal_entry_id = self.env['account.move'].sudo().create({
                    'move_type': 'entry',
                    'journal_id': self.source_journal_id.id if self.source_journal_id else False,
                    'company_id': self.location_id.company_id.id,
                    'currency_id': self.location_id.company_id.currency_id.id,
                    'ref': self.name + ' Source debit',
                    'line_ids': lines
                })
                source_journal_entry_id.action_post()

    def generate_destination_picking(self):
        """
        generate destination picking
        """
        picking_vals = {
            'partner_id': self.employee_id.sudo().work_contact_id.id,
            'location_id': self.transit_location_id and self.transit_location_id.id,
            'location_dest_id': self.dest_location_id and self.dest_location_id.id,
            'picking_type_id': self.custom_picking_trans_type_id.id,  # internal_obj.id,
            'note': self.reason,
            'custom_requisition_id': self.id,
            'origin': self.name,

        }
        stock_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        stock_id = stock_obj.sudo().create(picking_vals)
        lines = []
        for line in self.requisition_line_ids:
            if line.requisition_type == 'internal':
                pick_vals = self._prepare_dest_pick_vals(line, stock_id)
                move_id = move_obj.sudo().create(pick_vals)
                if (self.transfer_type == 'between_companies' and self.source_debit_account_id
                        and self.destination_credit_account_id):
                    lines.append((0, 0, {
                        'account_id': line.product_id.categ_id.with_company(
                            self.dest_location_id.company_id).property_stock_valuation_account_id.id,
                        'debit': line.with_company(self.location_id.company_id).product_id.standard_price * line.qty,
                        'credit': 0.0,
                        'display_type': 'product',
                        'name': line.product_id.name,
                    }))
        if (self.transfer_type == 'between_companies' and self.source_debit_account_id
                and self.destination_credit_account_id):
            lines.append((0, 0, {
                'account_id': self.destination_credit_account_id.id,
                'credit': sum(
                    [product.with_company(self.location_id.company_id).product_id.standard_price * product.qty for
                     product in self.requisition_line_ids]),
                'debit': 0.0,
                'display_type': 'product',
            }))
            dest_journal_entry_id = self.env['account.move'].sudo().create({
                'move_type': 'entry',
                'journal_id': self.destination_journal_id.id if self.destination_journal_id else False,
                'company_id': self.dest_location_id.company_id.id,
                'currency_id': self.dest_location_id.company_id.currency_id.id,
                'ref': self.name + ' destination credit',
                'line_ids': lines
            })
            dest_journal_entry_id.action_post()

    # endregion
