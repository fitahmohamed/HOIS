from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SubcontractorDeliveryRequest(models.Model):
    """Model Subcontractor.delivery.request for a SubcontractorDeliveryRequest module."""
    _name = 'subcontractor.delivery.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'subcontractor.delivery.request'
    _rec_name = "name"

    name = fields.Char(readonly=True)
    project_id = fields.Many2one("project.project", string=_("Project"), readonly=True)
    project_state = fields.Selection(related="project_id.state")
    contract_id = fields.Many2one("owner.contract", string=_("Sub-Contract"), readonly=True)
    date = fields.Date(string=_("Date"))
    confirmation_date = fields.Date(string=_("Confirmation Date"), readonly=True)
    reference = fields.Many2one("owner.contract", string=_("Contract"), readonly=True)
    type = fields.Selection([('initial', 'Initial'), ('final', 'Final')], string=_("Type"))
    state = fields.Selection(
        [('draft', 'Draft'), ('confirm', 'Confirmed'), ('reject', 'Rejected'),
         ('paid', 'Paid')], default='draft')
    subcontractor_delivery_request_line_ids = fields.One2many("subcontractor.delivery.request.line",
                                                              "subcontractor_delivery_request_id")
    deduction_line_ids = fields.One2many("sub.contract.delivery.deduction.allowance", "request_id",
                                         domain=[('main_type', '=', 'deduction')])
    allowance_line_ids = fields.One2many("sub.contract.delivery.deduction.allowance", "request_id",
                                         domain=[('main_type', '=', 'allowance')])
    total_line_cost = fields.Float(string=_('Total Line Cost'), compute='_compute_total_line_cost')
    total_deduction_cost = fields.Float(string=_('Total Deduction Cost'), compute='_compute_total_deduction_cost')
    total_allowance_cost = fields.Float(string=_('Total Allowance Cost'), compute='_compute_total_allowance_cost')
    total_cost = fields.Float(string=_('Total Cost'), compute='_compute_total_cost')
    # payment_id = fields.Many2one("account.payment", string=_('Payment'))
    bill_id = fields.Many2one("account.move", string=_('Bill'))
    is_cr = fields.Boolean(default=False)

    def _compute_total_line_cost(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.total_line_cost = sum([p.total_amount for p in rec.subcontractor_delivery_request_line_ids])

    def _compute_total_deduction_cost(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.total_deduction_cost = sum([p.amount for p in rec.deduction_line_ids])

    def _compute_total_allowance_cost(self):

        for rec in self:
            rec.total_allowance_cost = sum([p.amount for p in rec.allowance_line_ids])

    def _compute_total_cost(self):

        for rec in self:
            rec.total_cost = rec.total_line_cost - rec.total_deduction_cost - rec.total_allowance_cost

    @api.model
    def create(self, vals_list):
        """Create a new 'subcontractorDeliveryRequest' record with a unique name."""
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('subcontractor.delivery.request')
        res = super(SubcontractorDeliveryRequest, self).create(vals_list)
        return res

    def unlink(self):
        """
        Delete the current record if its state is 'draft'.

        :return: bool
            Returns True if the record is successfully deleted, otherwise raises an exception.
        """
        for rec in self:
            if rec.state not in ['draft']:
                raise UserError(_('You can not delete a Request which is in %s state.') % rec.state)
            return super().unlink()

    def action_confirm(self):
        """Confirm the completion request."""
        self.ensure_one()
        rejected_lines = self.subcontractor_delivery_request_line_ids.filtered(lambda x: x.state in (' ', 'reject') or x.amount == 0 or x.percentage == 0)
        if rejected_lines:
            raise UserError(_("You cannot confirm a request with rejected lines or blank lines."))
        for line in self.subcontractor_delivery_request_line_ids:
            if line.quantity == 0:
                raise UserError(_('Please enter quantity for %s.') % line.item_id.name)
        partially_approved_lines = self.subcontractor_delivery_request_line_ids.filtered(lambda x: x.state == 'partially')
        if partially_approved_lines:
            self.action_create_deductions(partially_approved_lines)
            self.action_create_contract_deductions(partially_approved_lines)
        if self.contract_id.down_payment_percentage > 0:
            self.action_create_allowances()
            self.action_create_contract_allowances()
        self.recompute_contract_qty()
        self.state = 'confirm'
        self.confirmation_date = fields.Date.today()

    def action_create_deductions(self, lines):
        """Create deductions for the specified lines."""
        for line in lines:
            self.env['sub.contract.delivery.deduction.allowance'].create({
                'name': 'Deduction for Item: ' + line.item_id.name,
                'item_id': line.item_id.id,
                'request_id': self.id,
                'main_type': 'deduction',
                'contract_type': 'subcontractor',
                'percentage': 1 - line.percentage,
                'amount': line.total_amount - line.amount
            })

    def action_create_allowances(self):
        """Create allowances based on the completion request."""
        self.env['sub.contract.delivery.deduction.allowance'].create({
            'name': 'Allowance for completion request: ' + self.name,
            'request_id': self.id,
            'main_type': 'allowance',
            'contract_type': 'subcontractor',
            'percentage': self.contract_id.down_payment_percentage,
            'amount': self.total_line_cost * self.contract_id.down_payment_percentage
        })

    def action_create_contract_deductions(self, lines):
        """Create deductions in the associated contract based on the completion request lines."""
        for line in lines:
            ded_line = self.contract_id.deduction_line_ids.filtered(lambda x: x.item_id == line.item_id)
            if ded_line:
                ded_line.ensure_one()
                ded_line.amount += (line.total_amount - line.amount)
                ded_line.clac_dedct_perc()
            else:
                item_tot = 0
                item_line = line.subcontractor_delivery_request_id.contract_id.owner_contract_line_ids.filtered(lambda x: x.item_id == line.item_id)
                if item_line:
                    for item in item_line:
                        item_tot += item.amount
                self.contract_id.deduction_line_ids.create({
                    'name': 'Deduction for Item: ' + line.item_id.name,
                    'contract_id': self.contract_id.id,
                    'main_type': 'deduction',
                    'contract_type': 'subcontractor',
                    'percentage': (line.total_amount - line.amount) / item_tot,
                    'amount': line.total_amount - line.amount,
                    'item_id': line.item_id.id
                })

    def action_create_contract_allowances(self):
        """Create allowances in the associated contract based on the completion request."""
        self.contract_id.allowance_line_ids.create({
            'name': 'Allowance for completion request: ' + self.name,
            'contract_id': self.contract_id.id,
            'main_type': 'allowance',
            'contract_type': 'owner',
            'percentage': self.contract_id.down_payment_percentage,
            'amount': self.total_line_cost * self.contract_id.down_payment_percentage
        })

    def recompute_contract_qty(self):
        """Recompute the contract quantity based on the completion request lines."""
        for line in self.contract_id.owner_contract_line_ids:
            delivery_request_line = self.subcontractor_delivery_request_line_ids.filtered(lambda x: x.item_id == line.item_id)
            if delivery_request_line:
                line.finished_quantity += delivery_request_line.quantity

    def action_reject(self):
        """Reject the completion request."""
        for rec in self:
            rec.state = 'reject'

    # def action_draft(self):
    #     for rec in self:
    #         rec.state = 'draft'

    # @api.depends('subcontractor_delivery_request_line_ids.amount')
    # def _compute_total_amount(self):
    #     for rec in self:
    #         rec.total_amount = sum(line.amount for line in rec.subcontractor_delivery_request_line_ids)
    @api.depends('quantity', 'price_unit')
    def _compute_total_amount(self):
        """Compute the total amount for each record by multiplying the quantity and price_unit values."""
        for rec in self:
            rec.total_amount = rec.price_unit * rec.quantity

    def create_bill(self):
        if not self.contract_id.partner_id:
            raise UserError(_('Please select a sub-contractor.'))

        delivery_journal_account_id = int(
            self.env['ir.config_parameter'].sudo().get_param('nthub_constructions.vendor_delivery_journal_account_id'))
        delivery_request_account_id = int(
            self.env['ir.config_parameter'].sudo().get_param('nthub_constructions.vendor_delivery_request_account_id'))

        if delivery_journal_account_id and delivery_request_account_id:
            bill = self.env['account.move'].sudo().create({
                'ref': self.name,
                'invoice_date': self.date,
                'partner_id': self.contract_id.partner_id.id,
                'journal_id': delivery_journal_account_id,
                'move_type': 'in_invoice',
                'invoice_line_ids': [(0, 0, {
                    'name': line.description or line.item_id.name,
                    'quantity': 1, # line.quantity,
                    'price_unit': line.amount,
                    'account_id': delivery_request_account_id,
                    'analytic_distribution': line.analytic_distribution,
                }) for line in self.subcontractor_delivery_request_line_ids]
            })
            if self.allowance_line_ids:
                for line in self.allowance_line_ids:
                    bill.invoice_line_ids.create({
                        'name': line.name,
                        'quantity': 1, # line.quantity,
                        'price_unit': line.amount * -1,
                        'account_id': delivery_request_account_id,
                    })
            self.bill_id = bill.id
            bill.action_post()
            self.state = 'paid'
        else:
            bill = self.env['account.move'].sudo().create({
                'ref': self.name,
                'invoice_date': self.date,
                'partner_id': self.contract_id.partner_id.id,
                'move_type': 'in_invoice',
                'invoice_line_ids': [(0, 0, {
                    'name': line.description or line.item_id.name,
                    'quantity': 1, # line.quantity,
                    'price_unit': line.amount,
                    'analytic_distribution': line.analytic_distribution,
                }) for line in self.subcontractor_delivery_request_line_ids]
            })
            if self.allowance_line_ids:
                for line in self.allowance_line_ids:
                    bill.invoice_line_ids.create({
                        'name': line.name,
                        'quantity': 1, # line.quantity,
                        'price_unit': line.amount * -1,
                        'account_id': delivery_request_account_id,
                    })
            self.bill_id = bill.id
            bill.action_post()
            self.state = 'paid'

    # def create_payment(self):
    #     if not self.contract_id.partner_id:
    #         raise UserError(_('Please select a sub-contractor.'))
    #     payment = self.env['account.payment'].create({
    #         'payment_type': 'outbound',
    #         'payment_method_id': self.env.ref('account.account_payment_method_manual_out').id,
    #         'partner_type': 'supplier',
    #         'partner_id': self.contract_id.partner_id.id,
    #         'amount': self.total_cost,
    #         'ref': self.name,
    #     })
    #     self.payment_id = payment.id
    #     self.state = 'paid'
    #     payment.action_post()
    # if self.contract_id.account_id:
    #     for rec in payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_current'):
    #         rec.write({'account_id': self.contract_id.account_id.id})

    def open_subcontractor_bill(self):
        """
        Open the bill associated with the delivery request.
        """
        if not self.bill_id:
            raise UserError(_("No Invoice associated with this subcontractor request."))
        return {
            'name': _('Bill'),
            'view_type': 'form',
            'res_id': self.bill_id.id,
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def combine_selected_records(self):
        """
        Combine selected records where state == 'confirm' and is_cr == False.
        """
        selected_records = self.filtered(lambda r: r.state != 'draft' and not r.is_cr)
        if len(selected_records) == 0:
            raise UserError(_("Select at least one Confirmed & uncombined previously delivery request."))
        item_quantities = {}
        item_prices = {}
        dl_projects = []
        for rec in selected_records:
            project_id = rec.project_id.id
            own_cont = self.env['owner.contract'].search([('project_id', '=', project_id), ('is_owner', '=', True)])
            if project_id not in dl_projects:
                dl_projects.append(project_id)
                if len(dl_projects) > 1:
                    raise UserError(_("You can not combine records from different projects."))
                if rec.project_id.state == 'done':
                    raise UserError(_("Project %s is already done. You can not combine records from a done project.") % rec.project_id.name)

            for line in rec.subcontractor_delivery_request_line_ids:
                item_id = line.item_id.id
                quantity = line.quantity
                if item_id in item_quantities:
                    item_quantities[item_id] += quantity
                else:
                    item_quantities[item_id] = quantity
                    own_cont_line = self.env['owner.contract.line'].search([('owner_contract_id', '=', own_cont[0].id), ('item_id', '=', item_id)])
                    item_prices[item_id] = own_cont_line.price_unit
            rec.is_cr = True
        new_record_values = {
            'project_id': selected_records[0].project_id.id,
            'contract_id': selected_records[0].contract_id.reference.id,
            'type': 'initial',
            'date': fields.Date.today(),
            'state': 'processing',
            'line_ids': [
                (0, 0, {
                    'item_id': item_id,
                    'quantity': quantity,
                    'description': 'Combined Data',
                    'price_unit': item_prices[item_id],
                }) for item_id, quantity in item_quantities.items()
            ],
        }
        new_record = self.env['project.completion.request'].create(new_record_values)
        for line in new_record.line_ids:
            line._calc_qty()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'context': {
                'default_project_id': new_record.project_id.id,
                'default_contract_id': new_record.contract_id.id,
                'default_date': new_record.date,
            },
        }


class SubcontractorDeliveryRequestLine(models.Model):
    """Model representing lines in the 'ProjectEngineerTechnical' module, tracking technical project details. """
    _name = 'subcontractor.delivery.request.line'
    _inherit = 'analytic.mixin'
    _description = 'subcontractor.delivery.request.line'
    _rec_name = "item_id"

    description = fields.Text(string=_("Description"))
    code = fields.Char(string=_("Code"))
    item_id = fields.Many2one("tender.item", string=_("Item"))
    uom_id = fields.Many2one("uom.uom", string=_("Uom"))
    quantity = fields.Float(string=_("Current Quantity"))
    price_unit = fields.Float(string=_("Price Unit"))
    percentage = fields.Float(string=_("Percentage"))
    amount = fields.Float(string=_("Approved Amount"))
    total_amount = fields.Float(string=_("Total Amount"), compute="_compute_total_amount", store=True)
    subcontractor_delivery_request_id = fields.Many2one("subcontractor.delivery.request",
                                                        string=_("Subcontractor Delivery Request"), ondelete="cascade")
    state = fields.Selection(
        [(' ', ' '), ('accept', 'Accepted'), ('partially', 'Partially Accepted'), ('reject', 'Rejected')],
        string=_("State"), default=' ')
    budget_amount = fields.Float(string='Budget Amount')


    @api.depends('quantity', 'price_unit')
    def _compute_total_amount(self):
        """Compute the total amount for each record by multiplying the quantity and price_unit values."""
        for rec in self:
            rec.total_amount = rec.price_unit * rec.quantity

    @api.onchange('percentage')
    def _onchange_percentage(self):
        """Onchange method triggered when the percentage is changed."""
        if self.percentage > 0:
            self.amount = self.total_amount * self.percentage
            if self.percentage == 1:
                self.state = 'accept'
            elif self.percentage > 0 and self.percentage < 1:
                self.state = 'partially'
        else:
            self.amount = 0
            self.state = 'reject'

    @api.onchange('amount')
    def _onchange_amount(self):
        """Onchange method triggered when the amount is changed."""
        if self.amount > 0:
            self.percentage = self.amount / self.total_amount
            if self.percentage == 1:
                self.state = 'accept'
            elif self.percentage > 0 and self.percentage < 1:
                self.state = 'partially'
        else:
            self.percentage = 0
            self.state = 'reject'

    @api.onchange('state')
    def _onchange_state(self):
        """Onchange method triggered when the state is changed."""
        if self.state == 'accept':
            self.amount = self.total_amount
            self.percentage = 1
        elif self.state == 'partially':
            self._onchange_amount()
        elif self.state == 'reject':
            self.percentage = 0
            self.amount = 0

    @api.onchange('item_id', 'quantity')
    def _calc_qty_subcontract(self):
        """Onchange method triggered when the quantity is changed."""
        for rec in self:
            if rec.item_id and rec.subcontractor_delivery_request_id:
                owner_contract_line = rec.env['owner.contract.line'].search([
                    ('owner_contract_id', '=', rec.subcontractor_delivery_request_id.contract_id.id),
                    ('item_id', '=', rec.item_id.id)
                ])
                completion_request_lines = self.env['subcontractor.delivery.request.line'].search([
                    ('subcontractor_delivery_request_id.project_id', '=', rec.subcontractor_delivery_request_id.project_id.id),
                    ('item_id', '=', rec.item_id.id),
                    ('subcontractor_delivery_request_id.state', '=', 'draft')
                ])
                cqty = sum(completion_request_lines.mapped('quantity'))
                c_remaining = owner_contract_line.remaining_quantity
                quantities = float(c_remaining) - float(cqty)
                if rec.quantity > quantities:
                    rec.quantity = max(0, quantities)
