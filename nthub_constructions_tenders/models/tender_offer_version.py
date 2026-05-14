from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TenderOfferVersion(models.Model):
    _name = 'tender.offer.version'
    _description = 'Tender Offer Version'

    name = fields.Char(string=_('Reference'), default='New', copy=False, readonly=True)
    customer_id = fields.Many2one('res.partner', string=_('Customer'), required=True)
    project_id = fields.Many2one("project.project", string=_("Project"))
    date = fields.Date(default=fields.Date.context_today, string=_('Date'))
    tag_ids = fields.Many2many('project.tags', related='project_id.tag_ids', string=_('Tags'))
    version_line_ids = fields.One2many('tender.offer.version.line', 'version_id', string=_('Version Line'))
    total_cost = fields.Float(string=_('Total Cost'), compute='_compute_total_cost')
    tender_offer_id = fields.Many2one('tender.offer', string=_('Tender Offer'), ondelete='cascade')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm')], tracking=True, default='draft', string=_('State'))
    description = fields.Char(string=_('Description'))

    @api.model
    def create(self, vals_list):
        """
        Create a new record and set the sequence."""
        for vals in vals_list:
            name = self.env['ir.sequence'].next_by_code('tender.offer.version')
            vals.update({
                'name': name,
            })
        return super(TenderOfferVersion, self).create(vals_list)

    def unlink(self):
        """
        Delete the current record if its state is 'draft'.

        :return: bool
            Returns True if the record is successfully deleted, otherwise raises an exception.
        """
        for rec in self:
            if rec.state not in ['draft']:
                raise UserError(_('You can not delete an Offer Version which is not in %s state.') % rec.state)
            return super().unlink()

    @api.depends('version_line_ids.sub_total')
    def _compute_total_cost(self):
        """
        Compute the total cost of the offer
        """
        for record in self:
            record.total_cost = sum(line.sub_total for line in record.version_line_ids)

    def action_confirm(self):
        """
        Set the state to 'confirm'
        """
        self.state = 'confirm'


class TenderOfferVersionLine(models.Model):
    _name = 'tender.offer.version.line'
    _description = 'Tender Offer Version Line'

    version_id = fields.Many2one('tender.offer.version', string=_('Version'), ondelete='cascade')
    item_id = fields.Many2one('tender.item', string=_('Item'), help='Item', copy=False, required=True)
    name = fields.Char(string=_('Description'))
    uom_id = fields.Many2one('uom.uom', string=_('Unit of Measure'))
    qty = fields.Float(string=_('Quantity'), default=0.0)
    unit_price = fields.Float(string=_('Unit Price'))
    sub_total = fields.Float(string=_('Subtotal'), compute='_compute_sub_total')
    template_id = fields.Many2one('tender.job.cost', string=_("Template"), domain="[('state', '=', 'approve')]")
    flag = fields.Selection(
        [('m', 'Material'), ('l', 'labour'), ('e', 'Expenses'), ('q', 'Equipment'), ('s', 'subcontractor')],
        string=_('Type'))

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

    def unlink(self):
        """
        Delete the current record if its state is 'draft'."""
        for rec in self:
            if rec.version_id.state != 'draft':
                raise UserError(_('Only draft state can be deleted'))
            super(TenderOfferVersionLine, rec).unlink()






