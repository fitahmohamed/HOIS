# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PropertyMaintenance(models.Model):
    """Property Maintenance Request"""
    _inherit = 'maintenance.request'

    property_id = fields.Many2one('property.details', string='Property')
    tenancy_id = fields.Many2one('tenancy.details')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id',
                                  string='Currency')
    landlord_id = fields.Many2one('res.partner', string='LandLord')
    maintenance_type_id = fields.Many2one('product.template', string='Type',
                                          domain=[('is_maintenance', '=', True)])
    price = fields.Float(related='maintenance_type_id.list_price',
                         string='Price')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    invoice_state = fields.Boolean(string='State')

    bill_id = fields.Many2one('account.move', string="Bill")
    bill_state = fields.Boolean(string="State ")

    invoice_count = fields.Integer(string="Invoice Count", compute="_compute_invoice_count")
    bill_count = fields.Integer(string="Bill Count", compute="_compute_bill_count")

    payment_from = fields.Selection([('customer', 'Customer'), ('vendor', 'Vendor')],
                                    string="Payment From", default="customer")
    payment_type = fields.Selection([('invoice', 'Invoice'), ('bill', 'Bill')],
                                    string="Payment Type", default="invoice")
    customer_id = fields.Many2one('res.partner', string="Customer")
    vendor_id = fields.Many2one('res.partner', string="Vendor")
    maintenance_product_ids = fields.One2many('maintenance.product.line',
                                              'maintenance_id')
    total_untaxed_amount = fields.Monetary(string="Total Untaxed Amount",
                                           compute="_compute_total_untaxed_amount")
    total = fields.Monetary(string="Total")

    rent_contract_id = fields.Many2one('tenancy.details', string="Rent Contract")
    sell_contract_id = fields.Many2one('property.vendor', string="Sell Contract")

    def action_crete_invoice(self):
        """Create Maintenance Invoice for Customer"""
        if not self.maintenance_product_ids:
            raise ValidationError(self.env._("Add Product for create invoice"))
        invoice_lines = [
            (0, 0, {
                'product_id': product.product_id.id,
                'name': product.description,
                'quantity': product.quantity,
                'price_unit': product.price_unit,
                'tax_ids': product.tax_ids.ids,
            }) for product in self.maintenance_product_ids
        ]
        data = {
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': invoice_lines,
            'maintenance_request_id': self.id
        }
        if self.payment_from == 'customer':
            if not self.customer_id:
                raise ValidationError(self.env._("Add customer to create invoice"))
            data['partner_id'] = self.customer_id.id
        else:
            if not self.vendor_id:
                raise ValidationError(self.env._("Add vendor to create invoice"))
            data['partner_id'] = self.vendor_id.id
        invoice_id = self.env['account.move'].sudo().create(data)
        invoice_post_type = self.env['ir.config_parameter'].sudo(
        ).get_param('rental_management.invoice_post_type')
        if invoice_post_type == 'automatically':
            invoice_id.action_post()
        self.invoice_id = invoice_id.id
        self.total = invoice_id.amount_total
        self.invoice_state = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'account.move',
            'res_id': invoice_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_crete_bill(self):
        """View Bills"""
        if not self.maintenance_product_ids:
            raise ValidationError(self.env._("Add Product for create bill"))
        bill_lines = [
            (0, 0, {
                'product_id': product.product_id.id,
                'name': product.description,
                'quantity': product.quantity,
                'price_unit': product.price_unit,
                'tax_ids': product.tax_ids.ids,
            }) for product in self.maintenance_product_ids
        ]
        data = {
            'move_type': 'in_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': bill_lines,
            'maintenance_request_id': self.id
        }
        if self.payment_from == 'customer':
            if not self.customer_id:
                raise ValidationError(self.env._("Add customer to create bill"))
            data['partner_id'] = self.customer_id.id
        else:
            if not self.vendor_id:
                raise ValidationError(self.env._("Add vendor to create bill"))
            data['partner_id'] = self.vendor_id.id

        bill_id = self.env['account.move'].sudo().create(data)
        invoice_post_type = self.env['ir.config_parameter'].sudo(
        ).get_param('rental_management.invoice_post_type')
        if invoice_post_type == 'automatically':
            bill_id.action_post()
        self.bill_id = bill_id.id
        self.total = bill_id.amount_total
        self.bill_state = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Bill',
            'res_model': 'account.move',
            'res_id': bill_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    @api.depends('maintenance_product_ids')
    def _compute_total_untaxed_amount(self):
        """Compute total Untaxed"""
        for rec in self:
            total_amount = 0.0
            if rec.maintenance_product_ids:
                for product in rec.maintenance_product_ids:
                    total_amount += product.price_subtotal
            rec.total_untaxed_amount = total_amount

    def _compute_invoice_count(self):
        """Compute invoice count"""
        for rec in self:
            rec.invoice_count = len(self.env['account.move'].sudo().search(
                [('maintenance_request_id', 'in', [rec.id]),
                 ('move_type', '=', 'out_invoice')]).mapped('maintenance_request_id').mapped('id'))

    def _compute_bill_count(self):
        """Compute bill count"""
        for rec in self:
            rec.bill_count = len(self.env['account.move'].sudo().search(
                [('maintenance_request_id', 'in', [rec.id]),
                 ('move_type', '=', 'in_invoice')]).mapped('maintenance_request_id').mapped('id'))

    def action_view_invoice(self):
        """View Invoices"""
        return {
            "name": "Invoices",
            "type": "ir.actions.act_window",
            "domain": [("maintenance_request_id", "=", self.id)],
            "view_mode": "list,form",
            'context': {'create': False},
            "res_model": "account.move",
            "target": "current",
        }

    def action_view_bills(self):
        """View Bills"""
        return {
            "name": "Bills",
            "type": "ir.actions.act_window",
            "domain": [("maintenance_request_id", "=", self.id)],
            "view_mode": "list,form",
            'context': {'create': False},
            "res_model": "account.move",
            "target": "current",
        }

    @api.model
    def get_maintenance_stats(self):
        """Get dashboard statics"""
        company_domain = [('company_id', 'in', self.env.companies.ids + [False])]
        # Maintenance Stages
        maintenance_sudo = self.env['maintenance.request']
        total_maintenances = maintenance_sudo.sudo().search_count(company_domain)
        in_progress_maintenances = maintenance_sudo.sudo().search_count(
            [('kanban_state', '=', 'normal')] + company_domain)
        blocked_maintenances = maintenance_sudo.sudo().search_count(
            [('kanban_state', '=', 'blocked')] + company_domain)
        done_maintenances = maintenance_sudo.sudo().search_count(
            [('kanban_state', '=', 'done')] + company_domain)
        corrective_maintenances = maintenance_sudo.sudo().search_count(
            [('maintenance_type', '=', 'corrective')] + company_domain)
        preventive_maintenances = maintenance_sudo.sudo().search_count(
            [('maintenance_type', '=', 'preventive')] + company_domain)
        cancelled_maintenances = maintenance_sudo.sudo().search_count(
            [("archive", "=", True)] + company_domain)

        today_date = fields.Date.today()
        start_datetime = datetime.combine(today_date, time.min)
        end_datetime = datetime.combine(today_date, time.max)

        due_today = maintenance_sudo.sudo().search_read(
            [('schedule_date', '>=', start_datetime),
             ('schedule_date', '<=', end_datetime)] + company_domain,
            ['id', 'name', 'property_id', 'request_date', 'user_id', 'category_id'])

        overdue = maintenance_sudo.sudo().search_read(
            [('schedule_date', '<', start_datetime),
             ('schedule_date', '<', end_datetime)] + company_domain,
            ['id', 'name', 'property_id', 'request_date', 'user_id', 'category_id'])

        corrective_counts = {i: 0 for i in range(1, 13)}
        preventive_counts = {i: 0 for i in range(1, 13)}

        maintenances = maintenance_sudo.sudo()._read_group(
            domain=company_domain,
            groupby=['create_date:month', 'maintenance_type'],
            aggregates=['id:count'],
            order='create_date:month'
        )

        for month_date, maintenance_type, count in maintenances:
            if maintenance_type == 'corrective':
                corrective_counts[month_date.month] = count
            elif maintenance_type == 'preventive':
                preventive_counts[month_date.month] = count

        month_wise_corrective = [corrective_counts[i] for i in range(1, 13)]
        month_wise_preventive = [preventive_counts[i] for i in range(1, 13)]

        maintenance_stats = [
            ['In Progress', 'Blocked', 'Done', 'Cancelled'],
            [in_progress_maintenances, blocked_maintenances, done_maintenances,
             cancelled_maintenances]
        ]

        current_year = datetime.now().year

        invoice_totals = {i: 0.0 for i in range(1, 13)}
        bill_totals = {i: 0.0 for i in range(1, 13)}

        account_move_domain = [
            ('maintenance_request_id', '!=', False),
            ('invoice_date', '>=', f'{current_year}-01-01'),
            ('invoice_date', '<=', f'{current_year}-12-31'),
            ('move_type', 'in', ['out_invoice', 'in_invoice']),
            ('payment_state', 'in', ['paid', 'partial', 'in_payment']),
            ('state', '=', 'posted'),
        ]

        invoices = self.env['account.move'].sudo()._read_group(
            domain=account_move_domain,
            groupby=['invoice_date:month', 'move_type'],
            aggregates=['amount_total:sum'],
            order='invoice_date:month'
        )

        for month_date, move_type, total_amount in invoices:
            if move_type == 'out_invoice':
                invoice_totals[month_date.month] = total_amount
            elif move_type == 'in_invoice':
                bill_totals[month_date.month] = total_amount

        month_wise_invoice_total = [invoice_totals[i] for i in range(1, 13)]
        month_wise_bill_total = [bill_totals[i] for i in range(1, 13)]

        property_wise_invoice_domain = [
            ('maintenance_request_id', '!=', False),
            ('move_type', 'in', ['out_invoice', 'in_invoice']),
            ('payment_state', 'in', ['paid', 'partial', 'in_payment']),
            ('state', '=', 'posted'),
        ]

        results = self.env['account.move'].sudo()._read_group(
            domain=property_wise_invoice_domain,
            groupby=['maintenance_request_id.property_id', 'move_type'],
            aggregates=['amount_total:sum'],
        )

        property_totals = {}

        currency_id = self.env.company.currency_id
        
        def _format_currency(amount):
            symbol = currency_id.symbol or ''
            amount = amount or 0.0
            if currency_id.position == 'before':
                return f'{symbol} {amount}'
            return f'{amount} {symbol}'

        for property_rec, move_type, total_amount in results:
            if not property_rec:
                continue

            prop_id = property_rec.id

            if prop_id not in property_totals:
                property_totals[prop_id] = {
                    'property': property_rec.display_name,
                    'invoice_amount': 0.0,
                    'bill_amount': 0.0,
                }


            if move_type == 'out_invoice':
                property_totals[prop_id]['invoice_amount'] = _format_currency(total_amount)
            elif move_type == 'in_invoice':
                property_totals[prop_id]['bill_amount'] = _format_currency(total_amount)

        property_wise_amount = list(property_totals.values())

        top_5 = self.env['maintenance.request'].sudo()._read_group(
            domain=[('equipment_id', '!=', False)],
            groupby=['equipment_id'],
            aggregates=['id:count'],
            order='id:count desc',
            limit=5
        )

        top_5_equipment_list = [equipment_rec.display_name for equipment_rec, _ in top_5]

        return {
            'total_maintenances': total_maintenances,
            'in_progress_maintenances': in_progress_maintenances,
            'blocked_maintenances': blocked_maintenances,
            'done_maintenances': done_maintenances,
            'corrective_maintenances': corrective_maintenances,
            'preventive_maintenances': preventive_maintenances,
            'due_today': due_today,
            'overdue': overdue,
            'maintenance_type': {
                'corrective': month_wise_corrective,
                'preventive': month_wise_preventive,
            },
            'maintenance_stats': maintenance_stats,
            'month_wise_invoice_total': month_wise_invoice_total,
            'month_wise_bill_total': month_wise_bill_total,
            'currency': currency_id.symbol,
            'currency_position': currency_id.position,
            'property_wise_amount': property_wise_amount,
            'top_5_equipment_list': top_5_equipment_list
        }


class MaintenanceProduct(models.Model):
    """Maintenance Product"""
    _inherit = 'product.template'

    is_maintenance = fields.Boolean(string='Maintenance')


class MaintenanceProductLine(models.Model):
    """Maintenance Product Line"""
    _name = 'maintenance.product.line'
    _description = __doc__
    _rec_name = "product_id"

    maintenance_id = fields.Many2one('maintenance.request', string="Maintenance")
    product_id = fields.Many2one('product.product', string="Product")

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id',
                                  string='Currency')

    quantity = fields.Integer(string="Quantity", default=1)
    description = fields.Char(string="Description")
    price_unit = fields.Monetary(string="Price")
    tax_ids = fields.Many2many('account.tax', string="Taxes",
                               domain=[('type_tax_use', '=', 'sale')])
    price_subtotal = fields.Monetary(string="Amount", compute="_compute_price_subtotal")

    @api.onchange('product_id')
    def _onchange_product_get_details(self):
        """Get product details"""
        for rec in self:
            rec.price_unit = rec.product_id.lst_price
            if rec.product_id.taxes_id:
                rec.tax_ids = rec.product_id.taxes_id.ids
            rec.description = rec.product_id.name

    @api.depends('product_id', 'quantity', 'price_unit')
    def _compute_price_subtotal(self):
        """Compute price subtotal"""
        for rec in self:
            total_amount = 0.0
            if rec.product_id:
                total_amount = rec.quantity * rec.price_unit
            rec.price_subtotal = total_amount
