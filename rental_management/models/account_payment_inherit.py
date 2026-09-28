# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _


class AccountPaymentTenancy(models.Model):
    """Extend account.payment to link with rent contract and auto-post journal entry"""
    _inherit = 'account.payment'

    tenancy_id = fields.Many2one(
        'tenancy.details',
        string='عقد الإيجار',
        readonly=True,
        store=True,
    )
    tenancy_property_id = fields.Many2one(
        related='tenancy_id.property_id',
        string='الوحدة / العقار',
        store=True,
    )
    tenancy_landlord_id = fields.Many2one(
        related='tenancy_id.property_landlord_id',
        string='المالك',
        store=True,
    )
    tenancy_seq = fields.Char(
        related='tenancy_id.tenancy_seq',
        string='رقم العقد',
        store=True,
    )
    tenancy_start_date = fields.Date(
        related='tenancy_id.start_date',
        string='بداية العقد',
    )
    tenancy_end_date = fields.Date(
        related='tenancy_id.end_date',
        string='نهاية العقد',
    )
    tenancy_payment_term = fields.Selection(
        related='tenancy_id.payment_term',
        string='دورية السداد',
    )
    tenancy_tenant_id = fields.Many2one(
        related='tenancy_id.tenancy_id',
        string='المستأجر',
    )
    tenancy_journal_entry_id = fields.Many2one(
        'account.move',
        string='قيد استحقاق المالك',
        readonly=True,
        copy=False,
    )
    tenancy_installment_id = fields.Many2one(
        'rent.invoice',
        string='القسط',
        compute='_compute_tenancy_installment_id',
    )
    payment_collector_id = fields.Many2one(
        'res.users',
        string='المحصل',
        default=lambda self: self.env.user,
        readonly=True,
        copy=False,
    )

    @api.depends('tenancy_id')
    def _compute_tenancy_installment_id(self):
        """Find the rent installment that created this payment receipt."""
        installments = self.env['rent.invoice'].sudo()
        for payment in self:
            payment.tenancy_installment_id = installments.search(
                [('rent_payment_id', '=', payment.id)],
                limit=1,
            )

    def action_post(self):
        """Override action_post to create journal entry after payment is posted"""
        res = super().action_post()
        for payment in self.filtered(lambda p: p.tenancy_id):
            payment._create_tenancy_journal_entry()
            # Write payment_state directly on linked rent.invoice records
            rent_invoices = self.env['rent.invoice'].search(
                [('rent_payment_id', '=', payment.id)])
            if rent_invoices:
                rent_invoices.write({'payment_state': 'paid'})
            # Post notification in contract chatter
            payment.tenancy_id.message_post(
                body=_(
                    '✅ تم تأكيد سند القبض <b>%s</b> بمبلغ <b>%s %s</b> بتاريخ %s'
                ) % (
                    payment.name or '',
                    payment.amount,
                    payment.currency_id.symbol or '',
                    payment.date,
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        return res

    def _create_tenancy_journal_entry(self):
        """
        Create accounting entry when rent payment is confirmed:
          DR  Tenant Receivable account  (partner = Tenant)
          CR  Landlord Payable account   (partner = Landlord)
        """
        self.ensure_one()

        # Get landlord account from settings
        landlord_account_id = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'rental_management.landlord_account_id') or 0
        )
        if not landlord_account_id:
            return  # Not configured — skip silently

        landlord_account = self.env['account.account'].browse(landlord_account_id)
        if not landlord_account.exists():
            return

        # Tenant receivable account
        tenant = self.tenancy_id.tenancy_id  # res.partner (المستأجر)
        landlord = self.tenancy_id.property_landlord_id  # res.partner (المالك)

        tenant_receivable = tenant.property_account_receivable_id
        if not tenant_receivable:
            tenant_receivable = self.env['account.account'].search(
                [('account_type', '=', 'asset_receivable'),
                 ('company_id', '=', self.company_id.id)], limit=1)

        if not tenant_receivable:
            return

        # دفتر اليومية من الإعدادات
        journal_param = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.rent_payment_journal_id')
        if journal_param and int(journal_param or 0):
            journal = self.env['account.journal'].browse(int(journal_param))
        else:
            journal = self.env['account.journal'].search(
                [('type', '=', 'general'),
                 ('company_id', '=', self.company_id.id)], limit=1)
        if not journal:
            return

        move_vals = {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.date,
            'ref': _('قيد استحقاق المالك | %s | %s') % (
                self.tenancy_seq or '', self.tenancy_property_id.name or ''),
            'tenancy_journal_id': self.tenancy_id.id,
            'line_ids': [
                (0, 0, {
                    'account_id': tenant_receivable.id,
                    'partner_id': tenant.id,
                    'name': _('إيجار مستحق على المستأجر – %s') % (
                        self.memo or self.tenancy_seq or ''),
                    'debit': self.amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': landlord_account.id,
                    'partner_id': landlord.id if landlord else False,
                    'name': _('إيجار مستحق للمالك – %s') % (
                        self.memo or self.tenancy_seq or ''),
                    'debit': 0.0,
                    'credit': self.amount,
                }),
            ],
        }

        move = self.env['account.move'].sudo().create(move_vals)
        move.action_post()
        self.tenancy_journal_entry_id = move.id

    def action_open_tenancy_journal_entry(self):
        """Open the linked rent journal entry"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rent Journal Entry'),
            'res_model': 'account.move',
            'res_id': self.tenancy_journal_entry_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
