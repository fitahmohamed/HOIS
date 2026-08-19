# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError
from num2words import num2words
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class PaymentMoveLine(models.Model):
    _name = 'payment.move.line'
    _description = 'Payment Move Line'

    payment_amount = fields.Float(string="Amount")
    payment_id = fields.Many2one(
        comodel_name='account.payment',
        string='Payment',
        required=True,
        index=True,
        auto_join=True,
        ondelete="cascade",
        check_company=True,
    )
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Journal Entry',
        related='payment_id.move_id',
        readonly=True,
        index=True,
        auto_join=True,
        ondelete="cascade",
        check_company=True,
    )
    journal_id = fields.Many2one(
        related='move_id.journal_id', store=True, precompute=True,
        index=True,
        copy=False,
    )
    company_id = fields.Many2one(
        related='move_id.company_id', store=True, readonly=True, precompute=True,
        index=True,
    )
    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='move_id.company_currency_id', readonly=True, store=True, precompute=True,
    )
    move_name = fields.Char(
        string='Number',
        related='move_id.name', store=True,
        index='btree',
    )
    parent_state = fields.Selection(related='move_id.state', store=True)
    date = fields.Date(
        related='move_id.date', store=True,
        copy=False,
        group_operator='min',
    )
    invoice_date = fields.Date(
        related='move_id.invoice_date', store=True,
        copy=False,
        group_operator='min',
    )
    ref = fields.Char(
        related='move_id.ref', store=True,
        copy=False,
        index='trigram',
    )
    name = fields.Char('Label')
    move_type = fields.Selection(related='move_id.move_type')
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Account',
        index=False,
        auto_join=True,
        ondelete="cascade",
        domain="[('account_type', '!=', 'asset_cash')]",
        check_company=True,
        required=True
    )
    balance_tax_excl = fields.Monetary(
        string='Balance',
        currency_field='company_currency_id',
        tracking=True,
        required=True
    )
    balance = fields.Monetary(
        string='Balance',
        currency_field='company_currency_id',
        compute='_compute_balance_tax_excl',
        store=True,
        readonly=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='move_id.currency_id', store=True, readonly=False, precompute=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
    )
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    tax_type = fields.Selection(
        selection=[('sale', 'Sales'), ('purchase', 'Purchases')],
        compute='_compute_tax_type', store=True)
    tax_ids = fields.Many2many('account.tax', string="Taxes", domain="[('type_tax_use', '=', tax_type)]")

    @api.depends('balance_tax_excl', 'tax_ids')
    def _compute_balance_tax_excl(self):
        for rec in self:
            total_tax = 0.0
            if rec.tax_ids:
                for tax in rec.tax_ids:
                    tax_amount = (rec.balance_tax_excl * tax.amount) / 100
                    total_tax += tax_amount
            rec.balance = rec.balance_tax_excl + total_tax

    @api.depends('payment_id.payment_type')
    def _compute_tax_type(self):
        for rec in self:
            if rec.payment_id.payment_type == 'inbound':
                rec.tax_type = 'sale'
            else:
                rec.tax_type = 'purchase'


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    move_line_id = fields.Many2one(comodel_name='payment.move.line')


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    transfer_type = fields.Selection([
        ('standard', 'Journal to Account'),
        ('account_to_journal', 'Account to Journal'),
        ('account_to_account', 'Account to Account Transfer'),
        ('account_to_accounts', 'Account to Multiple Accounts'),
        ('journal_to_journal', 'Journal to Journal Transfer'),
        ('multi_account', 'Journal to Multiple Accounts')
    ], string='Transfer Type', default='standard')

    source_account_id = fields.Many2one(
        'account.account',
        string='Source Account',
        domain="[('id', 'in', available_account_ids)]",
    )
    dest_account_id = fields.Many2one(
        'account.account',
        domain="[('id', 'in', available_account_ids)]",
        string='Destination Account',
    )
    dest_journal_id = fields.Many2one(
        'account.journal',
        string='Destination Journal',
        domain="[('type', 'in', ('bank', 'cash'))]"
    )
    transfer_description = fields.Text('Transfer Description')
    is_multi_dest_account = fields.Boolean('Is Multi Destination', compute='_compute_multi_dest')
    destination_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Destination Account',
        store=True, readonly=False,
        compute='_compute_destination_account_ids',
        domain=False,
        check_company=True,
    )
    available_account_ids = fields.Many2many(
        comodel_name='account.account',
        domain=False,
        compute='_compute_available_journal_ids'
    )
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    move_line_ids = fields.One2many(comodel_name='payment.move.line', inverse_name="payment_id")
    is_internal_transfer = fields.Boolean()
    memo = fields.Char()

    @api.depends('transfer_type')
    def _compute_multi_dest(self):
        for rec in self:
            rec.is_multi_dest_account = rec.transfer_type == 'multi_account'

    @api.onchange('transfer_type')
    def _onchange_transfer_type(self):
        self.is_internal_transfer = True

        if self.transfer_type == 'standard':
            self.payment_type = 'outbound'
        if self.transfer_type == 'account_to_journal':
            self.payment_type = 'inbound'
        if self.transfer_type != 'standard':
            self.partner_id = False
        if self.transfer_type != 'multi_account':
            self.move_line_ids = False
        if self.transfer_type != 'account_to_account':
            self.dest_account_id = False
        if self.transfer_type != 'account_to_accounts':
            self.source_account_id = False
        if self.transfer_type != 'journal_to_journal':
            self.dest_journal_id = False
            self.is_internal_transfer = False

    def _check_payment_method_line_id(self):
        for pay in self:
            if not pay.payment_method_line_id:
                raise ValidationError(_("Please define a payment method line on your payment."))

    def _get_report_base_filename(self):
        self.ensure_one()
        return f"Payment_{self.name or ''}_{self.partner_id.name or ''}"

    def _compute_amount_word(self, amount):
        for rec in self:
            if not amount:
                amount2word = "صفر" + rec.currency_id.arabic_name
                continue
            try:
                # Convert number to Arabic words with base currency name
                amount_words = num2words(
                    amount,
                    lang='ar',
                    to='currency',
                )
                _logger.info(f"======amount_words : {amount_words}")

                if 'ريالاً' in amount_words:
                    amount_words = amount_words.replace('ريالاً', rec.currency_id.arabic_name or '')
                elif 'ريالان' in amount_words:
                    amount_words = amount_words.replace('ريالان', rec.currency_id.arabic_name or '')
                elif 'ريالات' in amount_words:
                    amount_words = amount_words.replace('ريالات', rec.currency_id.arabic_name or '')
                elif 'ريال' in amount_words:
                    amount_words = amount_words.replace('ريال', rec.currency_id.arabic_name or '')
                _logger.info(f"======amount_words 3333333333 : {amount_words}")

                amount_words = amount_words.replace('هللة', rec.currency_id.arabic_cents_name or '')
                amount2word = " فقط " + amount_words.capitalize() + " لا غير"
                return amount2word
            except (ValueError, NotImplementedError) as e:
                amount2word = f"{amount:.2f} {rec.currency_id.arabic_name or ''}"
                _logger.error(f"Amount to words conversion failed {amount2word}: {str(e)}")

    @api.onchange('move_line_ids')
    def _onchange_update_payment(self):
        self.amount = sum(rec.balance for rec in self.move_line_ids)

    def _get_analytic_distribution(self, analytic_account_id):
        if not analytic_account_id:
            return False

        plan_id = analytic_account_id.plan_id.id
        if plan_id:
            return {str(analytic_account_id.id): 100.0}
        return False

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        self.ensure_one()
        write_off_line_vals = write_off_line_vals or {}

        if self.transfer_type in ['standard', 'account_to_journal']:
            line_vals_list = super(AccountPayment, self)._prepare_move_line_default_vals(
                write_off_line_vals, force_balance)

            # Add analytic distribution to standard payment lines
            analytic_distribution = self._get_analytic_distribution(self.analytic_account_id)
            if analytic_distribution:
                for line in line_vals_list:
                    line['analytic_distribution'] = analytic_distribution

            return line_vals_list

        elif self.transfer_type == 'account_to_account':
            if not self.source_account_id or not self.dest_account_id:
                raise UserError(_("Please select both source and destination accounts."))

            return [
                {
                    'name': _("Transfer from %s") % (self.source_account_id.name or _("Unknown Account")),
                    'account_id': self.source_account_id.id,
                    'debit': 0.0,
                    'credit': self.amount,
                    'currency_id': self.currency_id.id,
                    'partner_id': False,
                    'analytic_distribution': self._get_analytic_distribution(self.analytic_account_id),
                },
                {
                    'name': _("Transfer to %s") % self.dest_account_id.name,
                    'account_id': self.dest_account_id.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'currency_id': self.currency_id.id,
                    'partner_id': False,
                    'analytic_distribution': self._get_analytic_distribution(self.analytic_account_id),
                }
            ]

        elif self.transfer_type == 'account_to_accounts':
            if not self.source_account_id or not self.move_line_ids:
                raise UserError(_("Please select source account and add destination accounts."))

            lines = [{
                'name': _("Transfer from %s") % (self.source_account_id.name or _("Unknown Account")),
                'account_id': self.source_account_id.id,
                'debit': 0.0,
                'credit': self.amount,
                'currency_id': self.currency_id.id,
                'partner_id': False,
                'analytic_distribution': self._get_analytic_distribution(self.analytic_account_id),
            }]

            for line in self.move_line_ids:
                # Create the base line
                line_vals = {
                    'name': line.name or _("Transfer"),
                    'account_id': line.account_id.id,
                    'debit': line.balance_tax_excl if line.balance_tax_excl > 0 else 0.0,
                    'credit': -line.balance_tax_excl if line.balance_tax_excl < 0 else 0.0,
                    'currency_id': self.currency_id.id,
                    'partner_id': line.partner_id.id,
                    'tax_ids': line.tax_ids.ids,
                    'analytic_distribution': self._get_analytic_distribution(line.analytic_account_id),
                }
                lines.append(line_vals)

            return lines

        elif self.transfer_type == 'journal_to_journal':
            if not self.dest_journal_id:
                raise UserError(_("Please select destination journal."))

            if self.is_internal_transfer:
                # Use internal transfer account as intermediary
                transfer_account = self.company_id.transfer_account_id
                if not transfer_account:
                    raise UserError(_("Please configure a transfer account in your company settings."))

                source_account = self.journal_id.default_account_id
                dest_account = self.dest_journal_id.default_account_id

                if not source_account or not dest_account:
                    raise UserError(_("Both source and destination journals must have default accounts configured."))

                analytic_distribution = self._get_analytic_distribution(self.analytic_account_id)

                # First payment: from source journal to transfer account
                payment1_lines = [
                    {
                        'name': _("Transfer to %s") % (self.dest_journal_id.name or _("Unknown journal")),
                        'account_id': source_account.id,
                        'debit': 0.0,
                        'credit': self.amount,
                        'currency_id': self.currency_id.id,
                        'partner_id': False,
                        'analytic_distribution': analytic_distribution,
                    },
                    {
                        'name': _("Intermediate transfer to %s") % (self.dest_journal_id.name or _("Unknown journal")),
                        'account_id': transfer_account.id,
                        'debit': self.amount,
                        'credit': 0.0,
                        'currency_id': self.currency_id.id,
                        'partner_id': False,
                        'analytic_distribution': analytic_distribution,
                    }
                ]

                # Second payment: from transfer account to destination journal
                payment2_lines = [
                    {
                        'name': _("Intermediate transfer from %s") % (self.journal_id.name or _("Unknown journal")),
                        'account_id': transfer_account.id,
                        'debit': 0.0,
                        'credit': self.amount,
                        'currency_id': self.currency_id.id,
                        'partner_id': False,
                        'analytic_distribution': analytic_distribution,
                    },
                    {
                        'name': _("Transfer from %s") % (self.journal_id.name or _("Unknown journal")),
                        'account_id': source_account.id,
                        'debit': self.amount,
                        'credit': 0.0,
                        'currency_id': self.currency_id.id,
                        'partner_id': False,
                        'analytic_distribution': analytic_distribution,
                    }
                ]

                return self.payment_type == 'outbound' and payment1_lines or payment2_lines
            else:
                # Direct journal-to-journal transfer
                dest_account = self.dest_journal_id.default_account_id
                if not dest_account:
                    raise UserError(_("Destination journal must have a default account."))

                return [
                    {
                        'name': _("Transfer to %s") % (self.dest_journal_id.name or _("Unknown journal")),
                        'account_id': self.journal_id.default_account_id.id,
                        'debit': 0.0,
                        'credit': self.amount,
                        'currency_id': self.currency_id.id,
                        'partner_id': False,
                        'analytic_distribution': self._get_analytic_distribution(self.analytic_account_id),
                    },
                    {
                        'name': _("Transfer from %s") % (self.journal_id.name or _("Unknown journal")),
                        'account_id': dest_account.id,
                        'debit': self.amount,
                        'credit': 0.0,
                        'currency_id': self.currency_id.id,
                        'partner_id': False,
                        'analytic_distribution': self._get_analytic_distribution(self.analytic_account_id),
                    }
                ]

        elif self.transfer_type == 'multi_account':
            line_vals_list = super(AccountPayment, self)._prepare_move_line_default_vals(
                write_off_line_vals, force_balance)
            liquidity_line = line_vals_list[0]

            # lines = [{
            #     'name': liquidity_line['name'],
            #     'account_id': liquidity_line['account_id'],
            #     'debit': liquidity_line['debit'],
            #     'credit': liquidity_line['credit'],
            #     'currency_id': self.currency_id.id,
            #     'partner_id': self.partner_id.id,
            #     'analytic_distribution': self._get_analytic_distribution(self.analytic_account_id),
            # }]

            lines = [{
                'name': liquidity_line.get('name'),
                'account_id': liquidity_line.get('account_id'),
                'debit': 0.0,
                'credit': self.amount,
                'currency_id': self.currency_id.id,
                'partner_id': self.partner_id.id,
                'analytic_distribution': self._get_analytic_distribution(self.analytic_account_id),
            }]

            for line in self.move_line_ids:
                line_vals = {
                    'name': line.name or _("Distribution"),
                    'account_id': line.account_id.id,
                    'debit': line.balance_tax_excl if line.balance_tax_excl > 0 else 0.0,
                    'credit': -line.balance_tax_excl if line.balance_tax_excl < 0 else 0.0,
                    'currency_id': self.currency_id.id,
                    'partner_id': line.partner_id.id,
                    'tax_ids': line.tax_ids.ids,
                    'analytic_distribution': self._get_analytic_distribution(line.analytic_account_id),
                }
                lines.append(line_vals)

            return lines

    def action_post(self):
        for payment in self:
            if payment.transfer_type == 'account_to_account' and not payment.dest_account_id:
                raise UserError(_("Please select a destination account."))
            if payment.transfer_type == 'account_to_accounts' and not payment.source_account_id:
                raise UserError(_("Please select a source account."))
            if payment.transfer_type == 'journal_to_journal' and not payment.dest_journal_id:
                raise UserError(_("Please select a destination journal."))

        posted_payments = super(AccountPayment, self).action_post()
        payment = self.filtered(lambda pay: pay.is_internal_transfer and not pay.paired_internal_transfer_payment_id)
        _logger.info(f"======payment 3333 : {payment}")

        payment._create_paired_internal_transfer_payment()
        _logger.info(f"======payment.move_id.line_ids 3333 : {self.move_id.line_ids}")

        return posted_payments

    def _create_paired_internal_transfer_payment(self):

        for payment in self:
            vals = {
                'journal_id': payment.dest_journal_id.id,
                'dest_journal_id': payment.journal_id.id,
                'payment_type': payment.payment_type == 'outbound' and 'inbound' or 'outbound',
                'move_id': None,
                'memo': payment.memo,
                'paired_internal_transfer_payment_id': payment.id,
                'date': payment.date,
            }
            paired_payment = payment.copy(vals)
            paired_payment.write({'outstanding_account_id': payment.dest_journal_id.default_account_id.id})

            # paired_payment.move_id._post(soft=False)
            paired_payment.action_post()
            payment.paired_internal_transfer_payment_id = paired_payment

            lines = (payment.move_id.line_ids + paired_payment.move_id.line_ids).filtered(
                lambda l: l.account_id == payment.destination_account_id and not l.reconciled)
            lines.reconcile()

    @api.depends('partner_type')
    def _compute_destination_account_ids(self):
        self.destination_account_id = False
        for pay in self:
            if pay.partner_type == 'customer':
                # Receive money from invoice or send money to refund it.
                if pay.partner_id:
                    pay.destination_account_id = pay.partner_id.with_company(
                        pay.company_id).property_account_receivable_id
                else:
                    pay.destination_account_id = self.env['account.account'].with_company(pay.company_id).search([
                        *self.env['account.account']._check_company_domain(pay.company_id),
                        ('account_type', '=', 'asset_receivable'),
                    ], limit=1)
            elif pay.partner_type == 'supplier':
                # Send money to pay a bill or receive money to refund it.
                if pay.partner_id:
                    pay.destination_account_id = pay.partner_id.with_company(pay.company_id).property_account_payable_id
                else:
                    pay.destination_account_id = self.env['account.account'].with_company(pay.company_id).search([
                        *self.env['account.account']._check_company_domain(pay.company_id),
                        ('account_type', '=', 'liability_payable'),
                    ], limit=1)

    def print_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No journal entry available for this payment"))

        return self.env.ref('bi_print_journal_entries.journal_entry_report_id').report_action(self.move_id)

    @api.depends('payment_type', 'transfer_type')
    def _compute_available_journal_ids(self):
        domain = [
            '|',
            ('company_id', 'parent_of', self.env.company.id),
            ('company_id', 'child_of', self.env.company.id),
        ]
        if self.transfer_type in ('account_to_account', 'account_to_accounts'):
            domain.append(('type', '=', 'general'))
            account_domain = [('account_type', '!=', 'asset_cash')]

            accounts = self.env['account.account'].search(account_domain)
            journals = self.env['account.journal'].search(domain)

            for pay in self:
                pay.available_journal_ids = journals
                pay.available_account_ids = accounts
        else:
            domain.append(('type', 'in', ('bank', 'cash', 'credit')))
            accounts = self.env['account.account'].search([])

            journals = self.env['account.journal'].search(domain)
            for pay in self:
                pay.available_account_ids = accounts
                if pay.payment_type == 'inbound':
                    pay.available_journal_ids = journals.filtered('inbound_payment_method_line_ids')
                else:
                    pay.available_journal_ids = journals.filtered('outbound_payment_method_line_ids')

    def _generate_journal_entry(self, write_off_line_vals=None, force_balance=None, line_ids=None):
        if self.transfer_type in ('account_to_account', 'account_to_accounts'):
            need_move = self
        else:
            need_move = self.filtered(lambda p: not p.move_id and p.outstanding_account_id)

        assert len(self) == 1 or (not write_off_line_vals and not force_balance and not line_ids)

        move_vals = []
        for pay in need_move:
            move_vals.append({
                'move_type': 'entry',
                'ref': pay.memo,
                'date': pay.date,
                'journal_id': pay.journal_id.id,
                'company_id': pay.company_id.id,
                'partner_id': pay.partner_id.id,
                'currency_id': pay.currency_id.id,
                'partner_bank_id': pay.partner_bank_id.id,
                'line_ids': line_ids or [
                    Command.create(line_vals)
                    for line_vals in pay._prepare_move_line_default_vals(
                        write_off_line_vals=write_off_line_vals,
                        force_balance=force_balance,
                    )
                ],
                'origin_payment_id': pay.id,
            })

        moves = self.env['account.move'].create(move_vals)
        for pay, move in zip(need_move, moves):
            pay.write({'move_id': move.id, 'state': 'in_process'})

    @api.depends('company_id', 'partner_id')
    def _compute_journal_id(self):
        for payment in self:
            company = payment.company_id or self.env.company
            payment.journal_id = self.env['account.journal'].search([
                *self.env['account.journal']._check_company_domain(company),
                ('type', '=', 'cash'),
            ], limit=1)


    @api.model_create_multi
    def create(self, vals_list):
        res = super(AccountPayment, self).create(vals_list)
        for payment in res:
            if payment.amount <= 0:
                raise ValidationError("Balance must be greater than zero!")
        return res

    def write(self, vals):
        res = super(AccountPayment, self).write(vals)

        for payment in self:
            if payment.amount <= 0:
                raise ValidationError("Payment amount must be greater than zero!")
        return res