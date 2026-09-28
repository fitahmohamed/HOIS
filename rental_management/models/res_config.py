# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


DASHBOARD_THEMES = [
    ('Teal', 'Teal'),
    ('Amber', 'Amber'),
    ('Indigo', 'Indigo'),
    ('Rose', 'Rose'),
    ('Slate', 'Slate'),
    ('Forest', 'Forest'),
    ('Ocean', 'Ocean'),
    ('Plum', 'Plum'),
    ('Copper', 'Copper'),
    ('Sage', 'Sage'),
]


class RentalConfig(models.TransientModel):
    """Real estate config settings"""
    _inherit = 'res.config.settings'

    reminder_days = fields.Integer(string='Days', default=5,
                                   config_parameter='rental_management.reminder_days')
    sale_reminder_days = fields.Integer(string="Days ", default=3,
                                        config_parameter='rental_management.sale_reminder_days')
    invoice_post_type = fields.Selection([('manual', 'Invoice Post Manually'),
                                          ('automatically', 'Invoice Post Automatically')],
                                         string="Invoice Post",
                                         default='manual',
                                         config_parameter='rental_management.invoice_post_type')
    month_days = fields.Integer(string="Month Days",
                                default=30, config_parameter='rental_management.month_days')
    quarter_days = fields.Integer(string="Quarter Days",
                                  default=90, config_parameter='rental_management.quarter_days')
    year_days = fields.Integer(string="Year Days",
                               default=365, config_parameter='rental_management.year_days')
    half_year_days = fields.Integer(string="Half Year Days", default=183,
                                    config_parameter='rental_management.half_year_days')

    # Default Account Product
    installment_item_id = fields.Many2one(
        'product.product', string="Installment Item",
        default=lambda self: self.env.ref('rental_management.property_product_1',
                                          raise_if_not_found=False),
        config_parameter='rental_management.account_installment_item_id')

    # Landlord payable account for journal entry on payment confirmation
    landlord_account_id = fields.Many2one(
        'account.account',
        string='حساب المالك الدائن',
        config_parameter='rental_management.landlord_account_id',
        help='Account credited (and debited to tenant receivable) when a rent payment is posted')

    # دفتر يومية القيود الأوتوماتيكية
    rent_payment_journal_id = fields.Many2one(
        'account.journal',
        string='دفتر يومية قيود استحقاق المالك',
        domain="[('type', '=', 'general')]",
        config_parameter='rental_management.rent_payment_journal_id',
        help='الدفتر الذي يُسجَّل فيه القيد الأوتوماتيك (قيد استحقاق المالك) عند تأكيد سند القبض')
    commission_journal_id = fields.Many2one(
        'account.journal',
        string='دفتر يومية قيود العمولة',
        domain="[('type', '=', 'general')]",
        config_parameter='rental_management.commission_journal_id',
        help='الدفتر الذي يُسجَّل فيه القيد الأوتوماتيك عند تأكيد فاتورة العمولة')
    deposit_item_id = fields.Many2one(
        'product.product', string="Deposit Item",
        default=lambda self: self.env.ref('rental_management.property_product_2',
                                          raise_if_not_found=False),
        config_parameter='rental_management.account_deposit_item_id')
    broker_item_id = fields.Many2one(
        'product.product', string="Broker Commission Item",
        default=lambda self: self.env.ref('rental_management.property_product_3',
                                          raise_if_not_found=False),
        config_parameter='rental_management.account_broker_item_id')
    maintenance_item_id = fields.Many2one(
        'product.product', string="Maintenance Item",
        default=lambda self: self.env.ref('rental_management.property_product_4',
                                          raise_if_not_found=False),
        config_parameter='rental_management.account_maintenance_item_id')
    contract_penalty_item_id = fields.Many2one(
        'product.product', string="Contract Penalty Item",
        default=lambda self: self.env.ref('rental_management.property_product_5',
                                          raise_if_not_found=False),
        config_parameter='rental_management.contract_penalty_item_id')

    # Penalty Configurations
    is_penalty_applied = fields.Boolean(
        string="Is Any Penalty?", config_parameter="rental_management.is_penalty_applied")
    penalty_days_after_due_for_rent_contract = fields.Integer(
        string="Apply Penalty After (Days)", default="5",
        config_parameter="rental_management.penalty_days_after_due_for_rent_contract")
    penalty_percentage_for_rent_contract = fields.Integer(
        string="Rent Contract Percentage",
        config_parameter="rental_management.penalty_percentage_for_rent_contract")
    penalty_days_after_due_for_sale_contract = fields.Integer(
        string="Apply Penalty After (Days) ", default="5",
        config_parameter="rental_management.penalty_days_after_due_for_sale_contract")
    penalty_percentage_for_sale_contract = fields.Integer(
        string="Sale Contract Percentage",
        config_parameter="rental_management.penalty_percentage_for_sale_contract")

    report_color_config = fields.Char(
        config_parameter='rental_management.report_color_config', default="#f4f6f7",
        string="Report Color", help="Select a lighter color shade for better report readability.")

    contract_report_color = fields.Char(
        config_parameter='rental_management.contract_report_color',
        default="black", string="Contract Report Color")

    # Property Brochure Mail Configurations ===============================================
    # property Mail Template
    mail_template_title = fields.Char(
        related='company_id.property_mail_template_title',
        string="Property Mail Template Title", readonly=False)
    mail_template_description = fields.Text(
        related='company_id.property_mail_template_description',
        string="Property Mail Template Description", readonly=False)
    # image
    template_image = fields.Binary(
        related='company_id.mail_template_image',
        string="Property Mail Template Image", readonly=False)

    # section title
    mail_template_section_one_title = fields.Char(
        related='company_id.property_mail_section_one_title', readonly=False)
    mail_template_section_two_title = fields.Char(
        related='company_id.property_mail_section_two_title', readonly=False)
    mail_template_section_three_title = fields.Char(
        related='company_id.property_mail_section_three_title', readonly=False)
    # section description
    mail_template_section_one_description = fields.Text(
        related='company_id.property_mail_section_one_description', readonly=False)
    mail_template_section_two_description = fields.Text(
        related='company_id.property_mail_section_two_description', readonly=False)
    mail_template_section_three_description = fields.Text(
        related='company_id.property_mail_section_three_description', readonly=False)
    # next section title
    next_section_title = fields.Char(related='company_id.section_title', readonly=False)

    # Contract Mail Configurations
    # image
    contract_template_image = fields.Binary(related='company_id.contract_mail_template_image',
                                            string="Contract Mail Template Image", readonly=False)
    # mail template
    mail_template_id = fields.Many2one(
        'mail.template',
        config_parameter='rental_management.mail_template_id',
        default=lambda self: self.env.ref('rental_management.active_contract_mail_template_new',
                                          raise_if_not_found=False),
        domain="[('model', '=', 'tenancy.details')]")
    rent_reminder_contract_mail_template_id = fields.Many2one(
        'mail.template',
        config_parameter='rental_management.rent_reminder_contract_mail_template_id',
        default=lambda self: self.env.ref(
            'rental_management.tenancy_reminder_contract_mail_template_new',
            raise_if_not_found=False), domain="[('model', '=', 'tenancy.details')]")

    # Property Booking Mail Configurations
    # mail template
    booking_mail_template_id = fields.Many2one(
        'mail.template',
        config_parameter='rental_management.booking_mail_template_id',
        default=lambda self: self.env.ref('rental_management.property_book_mail_template_new',
                                          raise_if_not_found=False),
        domain="[('model', '=', 'property.vendor')]" )

    # Property Booking Mail Configurations
    # Image
    property_sold_mail_template_image = fields.Binary(
        related='company_id.sold_property_mail_template_image',
        string="Property Sold Mail Template Image", readonly=False)

    # mail template
    property_sold_mail_template_id = fields.Many2one(
        'mail.template',
        config_parameter='rental_management.property_sold_mail_template_id',
        default=lambda self: self.env.ref('rental_management.property_sold_mail_template_new',
                                          raise_if_not_found=False),
        domain="[('model', '=', 'property.vendor')]")

    # Default Service Quantity for Payment Terms
    quarterly_service_quantity = fields.Integer(
        string="Quarterly Service Quantity", default=1,
        config_parameter="rental_management.quarterly_service_quantity")
    half_yearly_service_quantity = fields.Integer(
        string="Half Yearly Service Quantity", default=1,
        config_parameter="rental_management.half_yearly_service_quantity")

    # dashboard config
    dashboard_theme = fields.Selection(
        selection=DASHBOARD_THEMES,
        string='Dashboard Theme',
        default='Teal',
        config_parameter='rental_management.dashboard_theme',
        help='Select a colour theme that will be applied globally to the rental dashboard.',
    )

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('rental_management.dashboard_theme', self.dashboard_theme or 'Teal')

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res['dashboard_theme'] = ICP.get_param('rental_management.dashboard_theme', default='Teal')
        return res


    @api.constrains('reminder_days', 'sale_reminder_days', 'month_days', 'quarter_days',
                    'year_days', 'half_year_days')
    def _check_values_is_not_negative(self):
        """Raise Validation if value is negative"""
        for rec in self:
            if rec.reminder_days and rec.reminder_days < 0:
                raise ValidationError(self.env._(
                    "Reminder days for creating tenancy invoice must be zero or greater"))
            if rec.sale_reminder_days and rec.sale_reminder_days < 0:
                raise ValidationError(self.env._(
                    "Reminder days for creating invoice must be zero or greater"))
            if rec.month_days and rec.month_days < 0:
                raise ValidationError(self.env._("Month days must be zero or greater"))
            if rec.quarter_days and rec.quarter_days < 0:
                raise ValidationError(self.env._("Quarter days must be zero or greater"))
            if rec.year_days and rec.year_days < 0:
                raise ValidationError(self.env._("Year days must be zero or greater"))
            if rec.half_year_days and rec.half_year_days < 0:
                raise ValidationError(self.env._("Half year days must be zero or greater"))

    def action_reset_color(self):
        """Reset both colors and write into config parameters"""
        icp = self.env['ir.config_parameter'].sudo()
        # update system parameters
        icp.set_param('rental_management.report_color_config', "#f4f6f7")
        icp.set_param('rental_management.contract_report_color', "black")

        # update the transient record values so UI shows updated values
        for rec in self:
            rec.report_color_config = "#f4f6f7"
            rec.contract_report_color = "black"
