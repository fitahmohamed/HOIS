from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TenderOffer(models.Model):
    _name = 'tender.offer'
    _description = 'Tender Offer'

    name = fields.Char(string=_('Reference'), default='New', copy=False, readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved'), ('cancel', 'Cancel')], tracking=True,
                             default='draft', string=_('State'))
    customer_id = fields.Many2one('res.partner', string=_('Customer'), required=True)
    project_id = fields.Many2one("project.project", string=_("Project"))
    date = fields.Date(default=fields.Date.context_today, string=_('Date'))
    version_id = fields.Many2one('tender.offer.version', string=_('Version'),
                                 domain="[('tender_offer_id', '=', id),('state', '=', 'confirm')]", copy=False)
    tag_ids = fields.Many2many('project.tags', related='project_id.tag_ids', string=_('Tags'))
    order_line_ids = fields.One2many('tender.offer.line', 'tender_offer_id', string=_('Tender Offer Lines'))
    total_cost = fields.Float(string=_('Total Cost'), compute='_compute_total_cost')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string=_('Company'))
    currency_id = fields.Many2one('res.currency', string=_('Currency'))
    version_count = fields.Integer(string=_('Version'), compute='get_version_count')
    last_update_date = fields.Date(related='version_id.date', string=_('Last Update'))
    project_extra_expenses_ids = fields.One2many('project.extras', related='project_id.project_extras_ids')
    total_extra_cost = fields.Float(related='project_id.total_extra_cost', string=_('Total Extra Cost'))
    offer_total = fields.Float(string=_('Total Cost'), compute='_compute_offer_total')
    down_payment = fields.Float(string=_("Down Payment"))
    down_payment_percentage = fields.Float(string=_("Down Payment Percentage"))
    top_sheet_id = fields.Many2one('top.sheet', string=_('Related Top Sheet'))

    @api.model
    def create(self, vals_list):
        """
        Create a new record and set the sequence."""
        for vals in vals_list:
            name = self.env['ir.sequence'].next_by_code('tender.offer')
            vals.update({
                'name': name,
            })
        return super(TenderOffer, self).create(vals_list)

    def unlink(self):
        """
        Delete the current record if its state is 'draft'.

        :return: bool
            Returns True if the record is successfully deleted, otherwise raises an exception.
        """
        for rec in self:
            if rec.state not in ['draft']:
                raise UserError(_('You can not delete an Offer which is in %s state.') % rec.state)
            return super().unlink()

    @api.depends('order_line_ids.sub_total')
    def _compute_total_cost(self):
        """
        Compute the total cost of the offer
        """
        for record in self:
            record.total_cost = sum(line.sub_total for line in record.order_line_ids)

    @api.depends('total_extra_cost', 'total_cost')
    def _compute_offer_total(self):
        """
        Compute the total cost of the offer
        """
        for rec in self:
            rec.offer_total = rec.total_extra_cost + rec.total_cost

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """
        Set the currency of the offer
        """
        for rec in self:
            rec.currency_id = rec.company_id.currency_id.id

    @api.onchange('version_id')
    def onchange_version_id(self):
        """
        Set the order lines of the offer
        """
        order_lines = []
        self.order_line_ids = None
        for rec in self:
            for version_line in rec.version_id.version_line_ids:
                order_lines.append((0, 0, {
                    'item_id': version_line.item_id.id,
                    'name': version_line.name,
                    'uom_id': version_line.uom_id.id,
                    'template_id': version_line.template_id.id,
                    'qty': version_line.qty,
                    'unit_price': version_line.unit_price,
                }))
            rec.order_line_ids = order_lines

    @api.onchange('down_payment_percentage')
    def _onchange_down_payment_percentage(self):
        """
        Set the down payment of the offer
        """
        for rec in self:
            if rec.down_payment_percentage:
                rec.down_payment = rec.offer_total * rec.down_payment_percentage

    @api.onchange('down_payment')
    def _onchange_down_payment(self):
        """
        Set the down payment percentage of the offer
        """
        for rec in self:
            if 0 < rec.down_payment <= rec.offer_total:
                rec.down_payment_percentage = rec.down_payment / rec.offer_total
            else:
                rec.down_payment = 0
                rec.down_payment_percentage = 0

    def action_confirm(self):
        """
        Set the state of the offer to 'confirm'
        """
        for line in self.order_line_ids:
            if line.qty == 0:
                raise UserError(_('Please enter quantity for %s.') % line.item_id.name)
        self.state = 'approved'

    def action_cancel(self):
        """
        Set the state of the offer to 'cancel'
        """
        self.state = 'cancel'

    def create_new_version(self):
        """
        Create a new version for the offer
        """
        return {
            'name': "Select Version",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'new.version.wizard',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_tender_offer_id': self.id,
            },
            'target': 'new'
        }

    def get_version_count(self):
        """
        Get the number of versions for the offer
        """
        version = self.env['tender.offer.version'].search([('tender_offer_id', '=', self.id)])
        self.version_count = len(version)

    def action_open_version(self):
        """
        Open the version of the offer
        """
        return {
            'name': _('Version'),
            'domain': [('tender_offer_id', '=', self.id)],
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'tender.offer.version',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'target': 'current',
        }

    def action_create_top_sheet(self):
        """
        Create a new top sheet for the offer
        """
        existing_top_sheet = self.env['top.sheet'].search([('project_id', '=', self.project_id.id)], limit=1)
        if existing_top_sheet:
            raise UserError(_("A Top Sheet already exists for the selected project."))
        top_sheet_vals = {
            'project_id': self.project_id.id,
            'offer_id': self.id,
        }
        top_sheet = self.env['top.sheet'].create(top_sheet_vals)
        self.top_sheet_id = top_sheet.id
        return {
            'name': _('Top Sheet'),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'top.sheet',
            'res_id': top_sheet.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def action_open_top_sheet(self):
        """
        Open the top sheet for the offer
        """
        if not self.top_sheet_id:
            raise UserError(_("No Top Sheet is linked to this Tender Offer."))
        return {
            'name': _('Top Sheet'),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'top.sheet',
            'res_id': self.top_sheet_id.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

class TenderOfferLine(models.Model):
    _name = 'tender.offer.line'
    _description = 'Tender Offer Line'
    extra_expenses = fields.Boolean(string=_('Extra Expenses'))
    tender_offer_id = fields.Many2one('tender.offer', string=_('Tender Offer'), ondelete='cascade')
    item_id = fields.Many2one('tender.item', string=_('Item'), help='Item', copy=False, required=True)
    name = fields.Char(string=_('Description'))
    uom_id = fields.Many2one('uom.uom', string=_('Unit of Measure'))
    qty = fields.Float(string=_('Quantity'), default=0.0)
    unit_price = fields.Float(string=_('Unit Price'))
    sub_total = fields.Float(string=_('Subtotal'), compute='_compute_sub_total')
    flag = fields.Selection(
        [('m', 'Material'), ('l', 'labour'), ('e', 'Expenses'), ('q', 'Equipment'), ('s', 'subcontractor')],
        string=_('Type'))
    company_id = fields.Many2one('res.company', related='tender_offer_id.company_id', string=_('Company'))
    currency_id = fields.Many2one('res.currency', related='tender_offer_id.currency_id', string=_('Currency'))
    template_id = fields.Many2one('tender.job.cost', string=_("Template"), domain="[('state', '=', 'approve')]")

    @api.depends('item_id', 'qty', 'unit_price')
    def _compute_sub_total(self):
        """Update the sub_total field based on the qty and unit_price fields."""
        for record in self:
            record.sub_total = record.qty * record.unit_price

    @api.onchange('item_id')
    def _onchange_item_id(self):
        """Update the description and qty fields based on the selected item."""
        for rec in self:
            rec.name = rec.item_id.name
            rec.qty = 1.0
            rec.uom_id = rec.item_id.uom_id.id
