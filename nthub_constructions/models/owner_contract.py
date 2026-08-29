# -*- coding: utf-8 -*-
import math
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class OwnerContract(models.Model):
    _name = 'owner.contract'
    _description = 'owner.contract'

    name = fields.Char(readonly=True)
    project_id = fields.Many2one("project.project", string=_("Project"))
    project_state = fields.Selection(related='project_id.state')
    partner_id = fields.Many2one("res.partner", domain="[('is_subcontractor', '!=', is_owner)]")
    date = fields.Date(string=_("Start Date"))
    reference = fields.Many2one("owner.contract", string=_("Contract"))
    state = fields.Selection(
        [('draft', 'Draft'), ('confirm', 'Confirmed'), ('done', 'Done'),
         ], default='draft')
    # account_id = fields.Many2one("account.account", string='Account',
    #                                      compute='_compute_account_id')
    delivery_date = fields.Date(string=_("Delivery Date"))
    received_date = fields.Date(string=_("Received Date"))
    down_payment_percentage = fields.Float(string=_("Down Payment Percentage"))
    currency_id = fields.Many2one("res.currency", string=_("Currency"))
    down_payment = fields.Float(string=_("Down Payment"))
    is_owner = fields.Boolean(string=_("Is Owner"), default=True)
    # extra_expenses = fields.Float(string=_('Extra Expenses'))
    sub_contract_count = fields.Integer(string=_('Sub-Contracts'), compute='get_sub_contract_count')
    completion_request_count = fields.Integer(string=_('Completion Requests'), compute='get_completion_request_count')
    subcontractor_delivery_request_count = fields.Integer(string=_('Completion Requests'),
                                                          compute='get_subcontractor_delivery_request_count')
    owner_contract_line_ids = fields.One2many("owner.contract.line", "owner_contract_id")
    deduction_line_ids = fields.One2many("contract.deduction.allowance", "contract_id",
                                         domain=[('main_type', '=', 'deduction')])
    allowance_line_ids = fields.One2many("contract.deduction.allowance", "contract_id",
                                         domain=[('main_type', '=', 'allowance')])
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    deduction_total = fields.Float(string='Total Deductions', compute='_compute_deduction_total', store=True)
    allowance_total = fields.Float(string='Total Allowances', compute='_compute_allowance_total', store=True)
    total_after_deduction_allowance = fields.Float(string='Total After Deduction and Allowance',
                                                   compute='_compute_total_after_deduction_allowance', store=True)
    completed_total = fields.Float(string='Total Completed', compute='_compute_progress_totals', store=True)
    remaining_total = fields.Float(string='Total Remaining', compute='_compute_progress_totals', store=True)
    progress_rate = fields.Float(string='Completion Rate', compute='_compute_progress_totals', store=True)
    end_date = fields.Date(string=_('End Date'))
    generation_method = fields.Selection(
        [('progress', 'Progress'), ('duration', 'Duration')
         ])
    is_generated = fields.Boolean(string=_('Is Generated'))
    rate = fields.Float(string=_('Percentage'))
    months = fields.Integer(string=_('Months'))
    # invoice_id = fields.Many2one("account.move", string=_('Invoice'))
    payment_id = fields.Many2one("account.payment", string=_('Payment'))
    project_extra_expenses_ids = fields.One2many('project.extras', readonly=False, related='project_id.project_extras_ids')
    total_extra_cost = fields.Float(related='project_id.total_extra_cost', string=_('Total Extra Cost'))
    extra_expense_invoice_id = fields.Many2one('account.move', string=_('Extra Expenses Invoice'))

    @api.depends('total_amount', 'deduction_total', 'allowance_total', 'total_extra_cost')
    def _compute_total_after_deduction_allowance(self):
        """Compute the total amount after deduction and allowance for each record."""
        for rec in self:
            rec.total_after_deduction_allowance = rec.total_amount - rec.deduction_total - rec.allowance_total
            if rec.is_owner:
                rec.total_after_deduction_allowance += rec.total_extra_cost

    def action_create_expenses_invoice(self):
        """
        Create an expenses invoice for the current contract.

        This function creates an expenses invoice for the current contract by using the
        'account.move' model. The invoice is created with a reference indicating that it
        is for extra expenses related to the contract. The partner ID is set to the ID of
        the current partner. The move type is set to 'out_invoice' to indicate that it is
        an outgoing invoice. The invoice date is set to the current date. The invoice line
        items are created based on the 'project_extra_expenses_ids' records, with each
        record representing a product and its cost. The created invoice is then returned
        as a dictionary with information about the invoice.

        :return: A dictionary containing information about the created invoice.
        :rtype: dict
        """
        if not self.partner_id:
            raise UserError(_('Please select a customer.'))
        self.extra_expense_invoice_id = self.env['account.move'].create({
            'ref': _('Extra Expenses invoice') + ' for Contract ' + self.name,
            'partner_id': self.partner_id.id,
            'move_type': 'out_invoice',
            'invoice_date': datetime.now().date(),
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': rec.product_id.id,
                    'price_unit': rec.cost,
                    'quantity': 1,
                }) for rec in self.project_extra_expenses_ids],
        })
        return {
            'name': _('Extra expenses invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.extra_expense_invoice_id.id,
            'target': 'current',
        }

    def action_open_extra_expense_invoice(self):
        """
        Open the expenses invoice for the current contract.

        This function opens the expenses invoice for the current contract by using the
        'account.move' model. The invoice is then returned as a dictionary with information
        about the invoice.

        :return: A dictionary containing information about the created invoice.
        :rtype: dict
        """
        return {
            'name': _('Extra expenses invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.extra_expense_invoice_id.id,
            'target': 'current',
        }

    def action_generate_completion_request(self):
        """Generate completion requests based on the specified generation method."""
        self.is_generated = True
        if self.generation_method == 'progress':
            self._generate_progress_completion_requests()
        elif self.generation_method == 'duration':
            self._generate_duration_completion_requests()
        else:
            raise ValidationError(_('Please Select Generation Method'))

    def _generate_progress_completion_requests(self):
        """Generate progress-based completion requests."""
        no = math.ceil(100 / (self.rate * 100))
        for n in range(no):
            self._create_completion_request(False, n)

    def _generate_duration_completion_requests(self):
        """Generate duration-based completion requests."""
        if not self.date or not self.end_date:
            raise ValidationError(_('Please Fill Start Date and/or End Date'))
        else:
            mo = int((self.end_date - self.date).days / 30)
            no = int(mo / self.months)
            date = self.date
            for n in range(no):
                self._create_completion_request(date, 0)
                date += relativedelta(months=self.months)

    def _create_completion_request(self, date=False, n=0):
        """Create a completion request based on the contract's contract lines."""
        completion_request_model = self.env['project.completion.request']
        completion_request_lines = []
        for contract_line in self.owner_contract_line_ids:
            quantity, difference = self._calculate_quantity_and_difference(contract_line, n)
            line_data = {
                'item_id': contract_line.item_id.id,
                'description': contract_line.description,
                'uom_id': contract_line.uom_id.id if contract_line.uom_id else False,
                'price_unit': contract_line.price_unit,
                'percentage': 0,
                'quantity': quantity + difference,
            }
            completion_request_lines.append((0, 0, line_data))
        completion_request_vals = {
            'project_id': self.project_id.id,
            'contract_id': self.id,
            'date': date if self.generation_method == 'duration' else fields.Date.today(),
            'reference': self.name,
            'type': 'initial',
            'state': 'draft',
            'line_ids': completion_request_lines,
        }
        comple_request = completion_request_model.create(completion_request_vals)

    def _calculate_quantity_and_difference(self, contract_line, n):
        """Calculate quantity and difference based on the generation method."""
        if self.generation_method == 'progress':
            difference = 0
            quantity = int(contract_line.quantity / math.ceil(100 / (self.rate * 100)))
            if n == math.ceil(100 / (self.rate * 100)) - 1:
                difference = contract_line.quantity - (quantity * math.ceil(100 / (self.rate * 100)))
            return quantity, difference
        else:
            return contract_line.quantity, 0

    @api.depends('owner_contract_line_ids.amount')
    def _compute_total_amount(self):
        """Compute the total amount of the owner contract."""
        for rec in self:
            rec.total_amount = sum(line.amount for line in rec.owner_contract_line_ids)

    @api.depends('owner_contract_line_ids.completed_amount', 'owner_contract_line_ids.remaining_amount',
                 'total_amount')
    def _compute_progress_totals(self):
        """Compute the completed/remaining amounts and the overall completion rate of the contract."""
        for rec in self:
            rec.completed_total = sum(line.completed_amount for line in rec.owner_contract_line_ids)
            rec.remaining_total = sum(line.remaining_amount for line in rec.owner_contract_line_ids)
            rec.progress_rate = rec.completed_total / rec.total_amount if rec.total_amount else 0

    @api.model
    def create(self, vals_list):
        """Create a new owner contract."""
        for vals in vals_list:
            if vals['is_owner'] == True:
                vals['name'] = self.env['ir.sequence'].next_by_code('owner.contract')
                vals['name'] = 'OWN' + vals['name']
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('owner.contract')
                vals['name'] = 'SUB' + vals['name']
        res = super(OwnerContract, self).create(vals_list)
        return res

    def unlink(self):
        """
        Delete the current record if its state is 'draft'.
        :return: bool
            Returns True if the record is successfully deleted, otherwise raises an exception.
        """
        for rec in self:
            if rec.state not in ['draft']:
                raise UserError(_('You can not delete a Contract which is in %s state.') % rec.state)
            return super().unlink()

    def action_confirm(self):
        """
            Confirm the owner contract.
            This method updates the state of the owner contract to 'confirm'.
        """
        if not self.partner_id:
            raise UserError(_('Please select a Customer/Sub-contractor.'))
        for rec in self.owner_contract_line_ids:
            if rec.quantity == 0:
                raise UserError(_('Please enter quantity for %s.') % rec.item_id.name)
        self.state = 'confirm'

    def get_sub_contract_count(self):
        """Calculate and set the count of subcontractors associated with the owner contract."""
        for rec in self:
            rec.sub_contract_count = 0
            contracts = rec.env['owner.contract'].search([
                ('reference', '=', rec.name),
                ('is_owner', '=', False)
            ])
            rec.sub_contract_count = len(contracts)

    def get_completion_request_count(self):
        """Calculate and set the count of completion requests associated with the owner contract."""
        for rec in self:
            requests = rec.env['project.completion.request'].search([
                ('project_id', '=', rec.project_id.id)
            ])
            rec.completion_request_count = len(requests)

    def get_subcontractor_delivery_request_count(self):
        """Calculate and set the count of subcontractor delivery requests associated with the owner contract."""
        for rec in self:
            requests = rec.env['subcontractor.delivery.request'].search([
                ('contract_id', '=', rec.id)
            ])
            rec.subcontractor_delivery_request_count = len(requests)

    # @api.depends('is_owner')
    # def _compute_account_id(self):
    #     """Compute the revenue account based on whether the contract is for an owner or subcontractor."""
    #     for record in self:
    #         if record.is_owner:
    #             account_id = int(self.env['ir.config_parameter'].sudo().get_param('nthub_constructions.revenue_account_owner'))
    #             if account_id:
    #                 record.account_id = account_id
    #             else:
    #                 record.account_id = False
    #         else:
    #             account_id = int(self.env['ir.config_parameter'].sudo().get_param('nthub_constructions.expense_account_sub'))
    #             if account_id:
    #                 record.account_id = account_id
    #             else:
    #                 record.account_id = False


    def create_completion_request(self):
        """Create a completion request based on the owner contract."""
        completion_request_model = self.env['project.completion.request']
        # Collect information from all contract lines
        completion_request_lines = []
        for contract_line in self.owner_contract_line_ids:
            line_data = {
                'item_id': contract_line.item_id.id,
                'description': contract_line.description,
                'uom_id': contract_line.uom_id.id if contract_line.uom_id else False,
                'budget_amount': contract_line.budget_amount,
                'analytic_distribution': contract_line.analytic_distribution,
                'price_unit': contract_line.price_unit,
                'percentage': 0,
                'state': ' ',
            }
            completion_request_lines.append((0, 0, line_data))
        # Create a completion request with the collected data
        completion_request_vals = {
            'project_id': self.project_id.id,
            'contract_id': self.id,
            'date': date.today(),
            'reference': self.name,
            'type': 'initial',
            'state': 'draft',
            'line_ids': completion_request_lines,
        }
        comple_request = completion_request_model.create(completion_request_vals)
        return {
            'name': _('Completion Request'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'project.completion.request',
            "res_id": comple_request.id,
            'type': 'ir.actions.act_window',
            'target': 'current'
        }

    def action_open_completion_request(self):
        """Open completion requests associated with the owner contract."""
        completion_request_model = self.env['project.completion.request']
        # Query completion requests with the same project_id
        completion_requests = completion_request_model.search([('project_id', '=', self.project_id.id)])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Completion Templates',
            'res_model': 'project.completion.request',
            'view_mode': 'list,form',
            'domain': [('id', 'in', completion_requests.ids)],
            'target': 'current',
        }

    def create_sub_contract(self):
        """Create a sub-contract based on the owner contract."""
        sub_contract_model = self.env['owner.contract']
        # Collect information from all contract lines
        sub_contract_lines = []
        for contract_line in self.owner_contract_line_ids:
            line_data = {
                'code': contract_line.code,
                'item_id': contract_line.item_id.id,
                'description': contract_line.description,
                'uom_id': contract_line.uom_id.id if contract_line.uom_id else False,
                'quantity': 0,
                'budget_amount': contract_line.budget_amount,
                'analytic_distribution': contract_line.analytic_distribution,
                'price_unit': contract_line.price_unit,
                'percentage': 0,
                'amount': contract_line.amount,
            }
            sub_contract_lines.append((0, 0, line_data))
        # Create a single sub contract with all lines
        sub_contract_vals = {
            'project_id': self.project_id.id,
            'date': date.today(),
            'reference': self.id,
            'received_date': date.today(),
            'down_payment_percentage': 0,
            'currency_id': self.currency_id.id,
            'down_payment': 0,
            'is_owner': False,
            'owner_contract_line_ids': sub_contract_lines,
        }
        res = sub_contract_model.create(sub_contract_vals)
        return {
            'name': _('Sub Contract'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'owner.contract',
            "is_owner": False,
            "res_id": res.id,
            'type': 'ir.actions.act_window',
            'target': 'current'
        }

    def action_open_sub_contract(self):
        """Open the sub-contract records related to the current owner contract."""
        sub_contract_model = self.env['owner.contract']
        sub_contracts = sub_contract_model.search([('project_id', '=', self.project_id.id), ('is_owner', '=', False)])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sub Contract',
            'res_model': 'owner.contract',
            'view_mode': 'list,form',
            'domain': [('id', 'in', sub_contracts.ids)],
            'target': 'current',
        }

    def create_subcontractor_delivery_request(self):
        subcontractor_delivery_request_model = self.env['subcontractor.delivery.request']
        subcontractor_delivery_request_lines = []
        for contract_line in self.owner_contract_line_ids:
            line_data = {
                'item_id': contract_line.item_id.id,
                'description': contract_line.description,
                'uom_id': contract_line.uom_id.id if contract_line.uom_id else False,
                'budget_amount': contract_line.budget_amount,
                'analytic_distribution': contract_line.analytic_distribution,
                'price_unit': contract_line.price_unit,
                'percentage': 0,
                'state': ' ',
            }
            subcontractor_delivery_request_lines.append((0, 0, line_data))
        # Create a single completion request with all lines
        subcontractor_delivery_request_vals = {
            'project_id': self.project_id.id,
            'contract_id': self.id,
            'date': date.today(),
            'reference': self.reference.id,
            'type': 'initial',
            'state': 'draft',
            'subcontractor_delivery_request_line_ids': subcontractor_delivery_request_lines,
        }
        subcontractor_delivery_request = subcontractor_delivery_request_model.create(
            subcontractor_delivery_request_vals)
        return {
            'name': _('Subcontractor Completion Request'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'subcontractor.delivery.request',
            'res_id': subcontractor_delivery_request.id,
            'view_id': self.env.ref('nthub_constructions.subcontractor_delivery_request_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                'form_view_initial_mode': 'edit',
            },
            'target': 'current'
        }

    def action_open_subcontractor_delivery_request(self):
        """Open subcontractor delivery requests related to the current project in list and form view."""
        subcontractor_delivery_request_model = self.env['subcontractor.delivery.request']
        # Query completion requests with the same project_id
        subcontractor_delivery_requests = subcontractor_delivery_request_model.search(
            [('contract_id', '=', self.id)])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sub-Completion Templates',
            'res_model': 'subcontractor.delivery.request',
            'view_mode': 'list,form',
            'domain': [('id', 'in', subcontractor_delivery_requests.ids)],
            'target': 'current',
        }

    @api.depends('deduction_line_ids.amount')
    def _compute_deduction_total(self):
        """Compute the total amount of deductions for each record."""
        for rec in self:
            rec.deduction_total = sum(line.amount for line in rec.deduction_line_ids)

    @api.depends('allowance_line_ids.amount')
    def _compute_allowance_total(self):
        """Compute the total amount of allowances for each record."""
        for rec in self:
            rec.allowance_total = sum(line.amount for line in rec.allowance_line_ids)

    @api.onchange('down_payment_percentage')
    def _onchange_down_payment_percentage(self):
        """Onchange method triggered when the down payment percentage is changed."""
        for rec in self:
            if rec.down_payment_percentage:
                rec.down_payment = rec.total_amount * rec.down_payment_percentage

    @api.onchange('down_payment')
    def _onchange_down_payment(self):
        """Onchange method triggered when the down payment amount is changed."""
        for rec in self:
            if 0 < rec.down_payment <= rec.total_amount:
                rec.down_payment_percentage = rec.down_payment / rec.total_amount
            else:
                rec.down_payment = 0
                rec.down_payment_percentage = 0

    def create_payment(self):
        if not self.down_payment:
            raise UserError(_('Please enter a down payment amount.'))
        if not self.partner_id:
            raise UserError(_('Please select a customer.'))
        if self.down_payment > self.total_amount:
            raise UserError(_('The down payment amount cannot be greater than the total amount.'))
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
            'partner_type': 'customer',
            'partner_id': self.partner_id.id,
            'amount': self.down_payment,
            # 'ref': self.name,
        })
        self.payment_id = payment.id
        payment.action_post()

    # def create_invoice_from_down_payment(self):
    #     """Create an invoice from the down payment information."""
    #     # Define invoice values
    #     invoice_vals = {
    #         'invoice_date': self.date,
    #         'partner_id': self.partner_id.id,
    #         'move_type': 'out_invoice',
    #         'invoice_line_ids': [],
    #     }
    #     # Search for the product with the name 'Down Payment'
    #     product = self.env['product.product'].search([('name', '=', 'Down Payment')])
    #     # If the product doesn't exist, create it
    #     if not product:
    #         product = self.env['product.product'].create({
    #             'name': 'Down Payment',
    #         })
    #     # Create line values for the invoice
    #     line_vals = [(0, 0, {
    #         'product_id': product.id,
    #         'name': 'Down Payment',
    #         'quantity': 1,
    #         'price_unit': self.down_payment,
    #     })]
    #
    #     # Assign line values to invoice values
    #     invoice_vals['invoice_line_ids'] = line_vals
    #     # Create the invoice
    #     invoice = self.env['account.move'].create(invoice_vals)
    #     # Assign the created invoice to the current record
    #     self.invoice_id = invoice.id
    #     # Update the journal item
    #     if self.account_id:
    #         for rec in invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'income'):
    #             rec.write({'account_id': self.account_id.id})

    def create_payment_from_down_payment(self):
        if not self.down_payment:
            raise UserError(_('Please enter a down payment amount.'))
        if not self.partner_id:
            raise UserError(_('Please select a Sub-contractor.'))
        if self.down_payment > self.total_amount:
            raise UserError(_('The down payment amount cannot be greater than the total amount.'))
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'payment_method_id': self.env.ref('account.account_payment_method_manual_out').id,
            'partner_type': 'supplier',
            'partner_id': self.partner_id.id,
            'amount': self.down_payment,
            # 'ref': self.name,
        })
        self.payment_id = payment.id
        payment.action_post()
        # if self.account_id:
        #     for rec in payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_current'):
        #         rec.write({'account_id': self.account_id.id})


class OwnerContractLine(models.Model):
    _name = 'owner.contract.line'
    _inherit = 'analytic.mixin'
    _description = 'owner.contract.line'
    _rec_name = "item_id"

    item_id = fields.Many2one("tender.item", string=_("Item"))
    stage = fields.Many2one("constructions.stages", string=_("Stage"))
    code = fields.Char(string=_("Code"), related="item_id.code")
    description = fields.Text(string=_("Description"))
    job_id = fields.Many2one('tender.job', string=_("Related Job"), related="item_id.job_id")
    uom_id = fields.Many2one(related="item_id.uom_id", string=_("UOM"), store=True)
    quantity = fields.Float(string=_("Quantity"))
    finished_quantity = fields.Float(string=_("Finished Qty"))
    cost_price       = fields.Float(string=_("Cost Price"))
    profit_margin    = fields.Float(string=_("Profit Margin %"))
    sell_price       = fields.Float(string=_("Selling Price"))
    price_unit       = fields.Float(string=_("Price / Unit"))
    remaining_quantity = fields.Float(string=_("Remaining Quantity"), compute="_compute_remaining_quantity", store=True)
    percentage = fields.Float(string=_("Percentage"), compute="_compute_remaining_quantity",
                              inverse="_inverse_percentage", store=True, readonly=False,
                              help="Completion percentage. You can set it manually on running contracts "
                                   "(opening balance) and the finished/remaining quantities will be computed.")
    completed_amount = fields.Float(string=_("Completed Amount"), compute="_compute_remaining_quantity", store=True)
    remaining_amount = fields.Float(string=_("Remaining Amount"), compute="_compute_remaining_quantity", store=True)
    amount = fields.Float(string=_("Amount"), compute="_compute_amount", store=True)
    owner_contract_id = fields.Many2one("owner.contract", string=_("Owner Contract"), ondelete="cascade")
    template_id = fields.Many2one('tender.job.cost', string=_("Template"), domain="[('state', '=', 'approve')]")
    attachment = fields.Binary(string=_('Attachment'))
    budget_amount = fields.Float(string='Budget Amount', compute='_compute_budget_amount', store=True)

    @api.depends('analytic_distribution')
    def _compute_budget_amount(self):
        """ Computes the budget amount based on analytic distribution. """
        for rec in self:
            budget_amount = 0
            if rec.analytic_distribution:
                for key, value in rec.analytic_distribution.items():
                    analytic_account = self.env['account.analytic.account'].browse(int(key.split(",")[0]))
                    budget_line_ids = self.env['budget.line'].search([('account_id', '=', analytic_account.id)])
                    for budget_item in budget_line_ids:
                        budget_amount += budget_item.budget_amount * value / 100
                rec.budget_amount = budget_amount
            else:
                rec.budget_amount = 0

    @api.depends('quantity', 'finished_quantity', 'price_unit')
    def _compute_remaining_quantity(self):
        """Compute the remaining quantity based on the difference between the total quantity and the finished quantity."""
        for line in self:
            line.remaining_quantity = line.quantity - line.finished_quantity
            if line.quantity > 0:
                line.percentage = line.finished_quantity / line.quantity
            else:
                line.percentage = 0
            line.completed_amount = line.finished_quantity * line.price_unit
            line.remaining_amount = line.remaining_quantity * line.price_unit

    def _inverse_percentage(self):
        """Allow setting the completion percentage manually (e.g. opening balance for
        already-running contracts); it is converted to a finished quantity."""
        for line in self:
            if line.percentage < 0 or line.percentage > 1:
                raise ValidationError(_('Completion percentage must be between 0%% and 100%% for %s.')
                                      % (line.item_id.name or ''))
            line.finished_quantity = line.quantity * line.percentage

    @api.constrains('finished_quantity', 'quantity')
    def _check_finished_quantity(self):
        """Ensure the finished quantity stays between zero and the contract quantity."""
        for line in self:
            if line.finished_quantity < 0:
                raise ValidationError(_('Finished quantity cannot be negative for %s.')
                                      % (line.item_id.name or ''))
            if line.quantity and line.finished_quantity - line.quantity > 1e-6:
                raise ValidationError(_('Finished quantity cannot exceed the contract quantity for %s.')
                                      % (line.item_id.name or ''))

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.price_unit

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Update the price_unit field based on the selected template's jobcost_total."""
        if self.template_id:
            self.price_unit = self.template_id.jobcost_total

    @api.onchange('item_id', 'quantity')
    def _calc_qty(self):
        """Calculate quantity based on the selected item and contract, considering remaining quantity."""
        for rec in self:
            if not rec.owner_contract_id.is_owner:
                if rec.item_id and rec.owner_contract_id:
                    # Use a more explicit domain for improved readability
                    domain = [
                        ('owner_contract_id.id', '=', rec.owner_contract_id.reference.id),
                        ('item_id', '=', rec.item_id.id),
                        ('owner_contract_id.state', '=', 'confirm')
                    ]
                    owner_contract_line = rec.env['owner.contract.line'].search(domain, limit=1)
                    # print(owner_contract_line, 'owner_contract_line')

                    if owner_contract_line:
                        c_remaining = owner_contract_line.remaining_quantity
                        # print(c_remaining, rec.quantity, owner_contract_line, 'c_remaining, rec.quantity')

                        # Use min function to set quantity as the minimum of original quantity and remaining quantity
                        rec.quantity = min(rec.quantity, c_remaining)
