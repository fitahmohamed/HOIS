# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class OwnerVariationOrder(models.Model):
    _name = 'owner.variation.order'
    _description = 'Contract Variation Order'
    _rec_name = 'name'
    _order = 'date desc, id desc'

    # -------------------------------------------------------------------------
    # Basic Fields
    # -------------------------------------------------------------------------
    name = fields.Char(
        string='Reference', default='New', readonly=True, copy=False)

    state = fields.Selection([
        ('draft',     'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed',  'Reviewed'),
        ('approved',  'Approved'),
        ('executed',  'Executed'),
        ('rejected',  'Rejected'),
    ], default='draft', string='Status', copy=False, tracking=True)

    contract_id = fields.Many2one(
        'owner.contract', string='Main Contract',
        required=True, ondelete='restrict')

    project_id = fields.Many2one(
        related='contract_id.project_id', string='Project', store=True)
    partner_id = fields.Many2one(
        related='contract_id.partner_id', string='Customer', store=True)
    currency_id = fields.Many2one(
        related='contract_id.currency_id', string='Currency')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, string='Company')

    date = fields.Date(
        default=fields.Date.context_today, string='Date')
    reason = fields.Text(string='Reason')
    notes = fields.Text(string='Notes')

    line_ids = fields.One2many(
        'owner.variation.order.line', 'variation_order_id', string='Lines')

    # Available items from the selected contract (for domain filtering in lines)
    available_item_ids = fields.Many2many(
        'tender.item',
        compute='_compute_available_items',
        string='Contract Items')

    @api.depends('contract_id', 'contract_id.owner_contract_line_ids')
    def _compute_available_items(self):
        for rec in self:
            if rec.contract_id:
                rec.available_item_ids = (
                    rec.contract_id.owner_contract_line_ids.mapped('item_id'))
            else:
                rec.available_item_ids = self.env['tender.item']

    # -------------------------------------------------------------------------
    # Totals
    # -------------------------------------------------------------------------
    total_increase = fields.Float(
        compute='_compute_totals', store=True, string='Total Increase')
    total_decrease = fields.Float(
        compute='_compute_totals', store=True, string='Total Decrease')
    net_amount = fields.Float(
        compute='_compute_totals', store=True, string='Net Amount')

    @api.depends('line_ids.amount', 'line_ids.change_type')
    def _compute_totals(self):
        for rec in self:
            inc = sum(l.amount for l in rec.line_ids
                      if l.change_type in ('increase', 'new'))
            dec = sum(l.amount for l in rec.line_ids
                      if l.change_type == 'decrease')
            rec.total_increase = inc
            rec.total_decrease = dec
            rec.net_amount = inc - dec

    # -------------------------------------------------------------------------
    # Create: auto-sequence
    # -------------------------------------------------------------------------
    @api.model
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('owner.variation.order')
                    or 'New')
        return super().create(vals_list)

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        """Clear lines when contract changes to avoid stale item references."""
        for rec in self:
            if rec.line_ids:
                rec.line_ids = [(5,)]

    # -------------------------------------------------------------------------
    # Approval Cycle
    # -------------------------------------------------------------------------

    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Please add lines before submitting.'))
            if rec.state != 'draft':
                raise UserError(_('Can only submit from Draft state.'))
            rec.state = 'submitted'

    def action_review(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Can only review from Submitted state.'))
            rec.state = 'reviewed'

    def action_approve(self):
        for rec in self:
            if rec.state != 'reviewed':
                raise UserError(_('Can only approve after review engineer approves.'))
            rec.state = 'approved'

    def action_execute(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Variation order must be approved before execution.'))
            rec._apply_to_contract()
            rec.state = 'executed'

    def action_reject(self):
        for rec in self:
            if rec.state == 'executed':
                raise UserError(_('Cannot reject an already executed variation order.'))
            rec.state = 'rejected'

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('submitted', 'rejected'):
                raise UserError(
                    _('Can only reset to draft from Submitted or Rejected state.'))
            rec.state = 'draft'

    # -------------------------------------------------------------------------
    # Execution — apply to contract lines
    # -------------------------------------------------------------------------

    def _apply_to_contract(self):
        self.ensure_one()
        contract = self.contract_id

        for line in self.line_ids:
            existing = contract.owner_contract_line_ids.filtered(
                lambda cl, l=line: cl.item_id.id == l.item_id.id
            )

            if line.change_type == 'increase':
                if existing:
                    cl = existing[0]
                    new_qty = cl.quantity + line.quantity
                    price = line.unit_price if line.use_new_breakdown and line.unit_price else cl.price_unit
                    cl.write({
                        'quantity':   new_qty,
                        'price_unit': price,
                        'sell_price': price,
                        'amount':     new_qty * price,
                    })
                else:
                    self._create_contract_line(contract, line)

            elif line.change_type == 'decrease':
                if not existing:
                    raise UserError(
                        _('Item "%s" not found in the main contract, cannot apply decrease.')
                        % line.item_id.name)
                cl = existing[0]
                new_qty = cl.quantity - line.quantity
                if new_qty < 0:
                    raise UserError(
                        _('Final quantity for item "%s" would be negative (%.2f). '
                          'Please adjust the decrease quantity.')
                        % (line.item_id.name, new_qty))
                price = line.unit_price if line.use_new_breakdown and line.unit_price else cl.price_unit
                cl.write({
                    'quantity':   new_qty,
                    'price_unit': price,
                    'sell_price': price,
                    'amount':     new_qty * price,
                })

            elif line.change_type == 'new':
                if existing:
                    raise UserError(
                        _('Item "%s" already exists in the contract. '
                          'Use "Increase" instead of "New Item".')
                        % line.item_id.name)
                self._create_contract_line(contract, line)

    @staticmethod
    def _create_contract_line(contract, line):
        price = line.unit_price
        contract.write({'owner_contract_line_ids': [(0, 0, {
            'item_id':     line.item_id.id,
            'description': line.description or line.item_id.name,
            'uom_id':      line.uom_id.id if line.uom_id else False,
            'quantity':    line.quantity,
            'price_unit':  price,
            'cost_price':  price,
            'sell_price':  price,
            'amount':      line.quantity * price,
            'percentage':  0,
        })]})

    def action_open_contract(self):
        self.ensure_one()
        return {
            'name':      _('Main Contract'),
            'type':      'ir.actions.act_window',
            'res_model': 'owner.contract',
            'view_mode': 'form',
            'res_id':    self.contract_id.id,
            'target':    'current',
        }


class OwnerVariationOrderLine(models.Model):
    _name = 'owner.variation.order.line'
    _description = 'Variation Order Line'
    _rec_name = 'item_id'

    variation_order_id = fields.Many2one(
        'owner.variation.order', string='Variation Order',
        required=True, ondelete='cascade', index=True)

    # Contract items filtered to parent contract
    contract_id = fields.Many2one(
        related='variation_order_id.contract_id', string='Contract', store=False)

    item_id = fields.Many2one(
        'tender.item', string='Item', required=True)
    description = fields.Char(string='Description')
    uom_id = fields.Many2one('uom.uom', string='Unit')

    change_type = fields.Selection([
        ('increase', 'Increase'),
        ('decrease', 'Decrease'),
        ('new',      'New Item'),
    ], string='Change Type', required=True, default='increase')

    # Reference data from contract line (set by onchange, displayed readonly in view)
    ref_quantity   = fields.Float(string='Contract Qty',   default=0.0)
    ref_unit_price = fields.Float(string='Contract Price', default=0.0)

    # Option: use new price or keep old contract price
    use_new_breakdown = fields.Boolean(
        string='New Price?', default=False,
        help='Enable to override the contract unit price with a new one.')

    # Change values
    quantity   = fields.Float(string='Change Qty',  default=0.0)
    unit_price = fields.Float(string='Unit Price',  default=0.0)
    amount     = fields.Float(
        string='Amount', compute='_compute_amount', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_price

    @api.onchange('item_id')
    def _onchange_item_id(self):
        for rec in self:
            if not rec.item_id:
                continue
            rec.description = rec.item_id.name
            rec.uom_id = getattr(rec.item_id, 'uom_id', False)
            # Pull reference data from the matched contract line
            contract = rec.variation_order_id.contract_id
            if contract:
                matching = contract.owner_contract_line_ids.filtered(
                    lambda cl: cl.item_id.id == rec.item_id.id
                )
                if matching:
                    cl = matching[0]
                    rec.ref_quantity   = cl.quantity
                    rec.ref_unit_price = cl.price_unit
                    rec.uom_id = getattr(cl, 'uom_id', rec.uom_id)
                    rec.description = getattr(cl, 'description', rec.description) or rec.description
                    # Pre-fill unit price from contract unless user wants new breakdown
                    if not rec.use_new_breakdown:
                        rec.unit_price = cl.price_unit
                else:
                    rec.ref_quantity   = 0.0
                    rec.ref_unit_price = 0.0

    @api.onchange('use_new_breakdown')
    def _onchange_use_new_breakdown(self):
        """Reset unit price to contract reference when turning off new breakdown."""
        for rec in self:
            if not rec.use_new_breakdown and rec.ref_unit_price:
                rec.unit_price = rec.ref_unit_price

    @api.onchange('change_type')
    def _onchange_change_type(self):
        for rec in self:
            if rec.quantity < 0:
                rec.quantity = abs(rec.quantity)
