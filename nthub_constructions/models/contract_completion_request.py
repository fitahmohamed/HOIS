from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ProjectCompletionRequest(models.Model):
    """Model representing technical details for a project in the 'ProjectEngineerTechnical' module."""
    _name = 'project.completion.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'project.completion.request'
    _rec_name = "name"

    def _compute_total_line_cost(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.total_line_cost = sum([p.total_amount for p in rec.line_ids])

    def _compute_total_deduction_cost(self):
        """Compute the total line cost for each record by summing up the total_amount values of related line items."""
        for rec in self:
            rec.total_deduction_cost = sum([p.amount for p in rec.deduction_line_ids])

    def _compute_total_allowance_cost(self):
        """Compute the total allowance cost for each record by summing up the amount values of related allowance lines."""
        for rec in self:
            rec.total_allowance_cost = sum([p.amount for p in rec.allowance_line_ids])

    def _compute_total_cost(self):
        """Compute the total cost for each record by subtracting total deduction and total allowance costs from total line cost."""
        for rec in self:
            rec.total_cost = rec.total_line_cost - rec.total_deduction_cost - rec.total_allowance_cost

    name = fields.Char(readonly=True)
    project_id = fields.Many2one("project.project", string=_("Project"))
    contract_id = fields.Many2one("owner.contract", string=_("Contract"))
    date = fields.Date(string=_("Date"))
    confirmation_date = fields.Date(string=_("Confirmation Date"), readonly=True)
    reference = fields.Char(string=_("Reference"),readonly=True)
    type = fields.Selection([('initial', 'Initial'), ('final', 'Final')], string=_("Type"))
    state = fields.Selection(
        [('draft', 'Draft'), ('processing', 'Processing'), ('confirm', 'Confirmed'), ('reject', 'Rejected'),
         ('invoiced', 'Invoiced')], default='draft')
    line_ids = fields.One2many("project.completion.request.line", "completion_request_id")
    deduction_line_ids = fields.One2many("contract.completion.deduction.allowance", "request_id",
                                         domain=[('main_type', '=', 'deduction')])
    allowance_line_ids = fields.One2many("contract.completion.deduction.allowance", "request_id",
                                         domain=[('main_type', '=', 'allowance')])
    total_line_cost = fields.Float(string=_('Total Line Cost'), compute='_compute_total_line_cost')
    total_deduction_cost = fields.Float(string=_('Total Deduction Cost'), compute='_compute_total_deduction_cost')
    total_allowance_cost = fields.Float(string=_('Total Allowance Cost'), compute='_compute_total_allowance_cost')
    total_cost = fields.Float(string=_('Total Cost'), compute='_compute_total_cost')
    notes = fields.Text(string=_('Notes'))
    invoice_id = fields.Many2one('account.move', 'Invoice')

    @api.model
    def create(self,  vals_list):
        """Create a new 'ProjectEngineerTechnical' record with a unique name."""
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('project.completion.request')
        res = super(ProjectCompletionRequest, self).create(vals_list)
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

    def start_processing(self):
        """Update the state of the record to 'processing'."""
        for rec in self.line_ids:
            if rec.quantity == 0:
                raise UserError(_('Please enter quantity for %s.') % rec.item_id.name)
        self.state = 'processing'

    def action_confirm(self):
        """Confirm the completion request."""
        self.ensure_one()
        if not self.contract_id:
                raise UserError(_("Please select a contract."))

        # Check for rejected lines or blank lines
        rejected_lines = self.line_ids.filtered(lambda x: x.state in (' ', 'reject') or x.amount == 0 or x.percentage == 0)
        if rejected_lines:
            raise UserError(_("You cannot confirm a request with rejected lines or blank lines."))
        # Check for partially approved lines and create deductions
        partially_approved_lines = self.line_ids.filtered(lambda x: x.state == 'partially')
        if partially_approved_lines:
            self.action_create_deductions(partially_approved_lines)
            self.action_create_contract_deductions(partially_approved_lines)
        # Create allowances if down payment percentage is greater than 0
        if self.contract_id.down_payment_percentage > 0:
            self.action_create_allowances()
            self.action_create_contract_allowances()
        # Recompute contract quantity
        self.recompute_contract_qty()
        # Update state and confirmation date
        self.state = 'confirm'
        self.confirmation_date = fields.Date.today()

    def action_create_deductions(self, lines):
        """Create deductions for the specified lines."""
        for line in lines:
            self.env['contract.completion.deduction.allowance'].create({
                'name': 'Deduction for Item: ' + line.item_id.name,
                'item_id': line.item_id.id,
                'request_id': self.id,
                'main_type': 'deduction',
                'contract_type': 'owner',
                'percentage': 1 - line.percentage,
                'amount': line.total_amount - line.amount
            })

    def action_create_allowances(self):
        """Create allowances based on the completion request."""
        self.env['contract.completion.deduction.allowance'].create({
            'name': 'Allowance for completion request: ' + self.name,
            'request_id': self.id,
            'main_type': 'allowance',
            'contract_type': 'owner',
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
                item_line = line.completion_request_id.contract_id.owner_contract_line_ids.filtered(lambda x: x.item_id == line.item_id)
                if item_line:
                    for item in item_line:
                        item_tot += item.amount
                self.contract_id.deduction_line_ids.create({
                    'name': 'Deduction for Item: ' + line.item_id.name,
                    'contract_id': self.contract_id.id,
                    'main_type': 'deduction',
                    'contract_type': 'owner',
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
            completion_request_line = self.line_ids.filtered(lambda x: x.item_id == line.item_id)
            if completion_request_line:
                line.finished_quantity += completion_request_line.quantity

    def action_reject(self):
        for rec in self:
            rec.state = 'reject'

    # def action_draft(self):
    #     for rec in self:
    #         rec.contract_id.deduction_line_ids = [(5,)]
    #         rec.contract_id.allowance_line_ids = [(5,)]
    #         rec.deduction_line_ids = [(5,)]
    #         rec.allowance_line_ids = [(5,)]
    #         rec.state = 'draft'

    def create_completion_invoice(self):
        """
        Create an invoice based on the completion request.
        """
        for rec in self:
            if rec.state != 'confirm':
                raise UserError(_("You can only create an invoice for confirmed completion requests."))
            if not rec.contract_id.partner_id:
                raise UserError(_("Please select a customer on contract."))

            customer_compilation_journal_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
                'nthub_constructions.customer_compilation_journal_account_id'))
            customer_compilation_request_account_id = int(self.env['ir.config_parameter'].sudo().get_param(
                'nthub_constructions.customer_compilation_request_account_id'))

            if customer_compilation_journal_account_id and customer_compilation_request_account_id:
                invoice_vals = {
                    'partner_id': rec.contract_id.partner_id.id,
                    'invoice_date': rec.date,
                    'journal_id': customer_compilation_journal_account_id,
                    'currency_id': rec.contract_id.currency_id.id,
                    'move_type': 'out_invoice',
                    'invoice_line_ids': [],
                }

                for line in rec.line_ids:
                    # analytic_dist = {}
                    # if rec.project_id.analytic_account_id:
                    #     analytic_dist = {rec.project_id.analytic_account_id.id: 100}
                    invoice_line_vals = {
                        'product_id': line.item_id.related_product_id.id,
                        'name': line.item_id.name,
                        'analytic_distribution': line.analytic_distribution,
                        'quantity': 1,
                        'price_unit': line.amount,
                        'account_id': customer_compilation_request_account_id,
                    }
                    invoice_vals['invoice_line_ids'].append((0, 0, invoice_line_vals))
                    if rec.allowance_line_ids:
                        for line in rec.allowance_line_ids:
                            invoice_line_vals = {
                                'product_id': line.item_id.related_product_id.id,
                                'name': line.item_id.name,
                                'quantity': 1,
                                'price_unit': line.amount * -1,
                                'account_id': customer_compilation_request_account_id,
                            }
                            invoice_vals['invoice_line_ids'].append((0, 0, invoice_line_vals))
            else:
                invoice_vals = {
                    'partner_id': rec.contract_id.partner_id.id,
                    'invoice_date': rec.date,
                    'currency_id': rec.contract_id.currency_id.id,
                    'move_type': 'out_invoice',
                    'invoice_line_ids': [],
                }

                for line in rec.line_ids:
                    # analytic_dist = {}
                    # if rec.project_id.analytic_account_id:
                    #     analytic_dist = {rec.project_id.analytic_account_id.id: 100}
                    invoice_line_vals = {
                        'product_id': line.item_id.related_product_id.id,
                        'name': line.item_id.name,
                        'analytic_distribution': line.analytic_distribution,
                        'quantity': 1,
                        'price_unit': line.amount,
                    }
                    invoice_vals['invoice_line_ids'].append((0, 0, invoice_line_vals))
                if rec.allowance_line_ids:
                    for line in rec.allowance_line_ids:
                        invoice_line_vals = {
                            'product_id': line.item_id.related_product_id.id,
                            'name': line.item_id.name,
                            'quantity': 1,
                            'price_unit': line.amount * -1,
                        }
                        invoice_vals['invoice_line_ids'].append((0, 0, invoice_line_vals))

            invoice = self.env['account.move'].create(invoice_vals)
            rec.invoice_id = invoice.id
            invoice.action_post()
            rec.write({'state': 'invoiced'})

    def open_completion_invoice(self):
        """Open the associated invoice for the completion request."""
        if not self.invoice_id:
            raise UserError(_("No invoice associated with this completion request."))
        return {
            'name': _('Invoice'),
            'view_type': 'form',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }


class ProjectEngineerTechnicalLine(models.Model):
    """Model representing lines in the 'ProjectEngineerTechnical' module, tracking technical project details. """
    _name = 'project.completion.request.line'
    _inherit = 'analytic.mixin'
    _description = 'project.completion.request.line'
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
    completion_request_id = fields.Many2one("project.completion.request", string=_("Completion Request"),
                                            ondelete="cascade")
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
    def _calc_qty(self):
        """Calculate quantity based on the selected item and contract, considering remaining quantity."""
        for rec in self:
            if rec.item_id and rec.completion_request_id:
                owner_contract_line = rec.env['owner.contract.line'].search([
                    ('owner_contract_id', '=', rec.completion_request_id.contract_id.id),
                    ('item_id', '=', rec.item_id.id)
                ])

                completion_request_lines = self.env['project.completion.request.line'].search([
                    ('completion_request_id.project_id', '=', rec.completion_request_id.project_id.id),
                    ('item_id', '=', rec.item_id.id),
                    '|',
                    ('completion_request_id.state', '=', 'processing'),
                    ('completion_request_id.state', '=', 'draft')
                ])

                cqty = sum(completion_request_lines.mapped('quantity'))
                c_remaining = owner_contract_line.remaining_quantity
                quantities = float(c_remaining) - float(cqty)
                if rec.quantity > quantities:
                    rec.quantity = max(0, quantities)
