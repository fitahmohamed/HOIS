from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TenderOffer(models.Model):
    _name = 'tender.offer'
    _description = 'Tender Offer'

    name = fields.Char(string=_('Reference'), default='New', copy=False, readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved'), ('cancel', 'Cancel')], tracking=True,
                             default='draft', string=_('Status'))
    customer_id = fields.Many2one('res.partner', string=_('Customer'), required=True)
    project_id = fields.Many2one("project.project", string=_("Project"))
    date = fields.Date(default=fields.Date.context_today, string=_('Date'))
    version_id = fields.Many2one('tender.offer.version', string=_('Version'),
                                 domain="[('tender_offer_id', '=', id),('state', '=', 'confirm')]", copy=False)
    tag_ids = fields.Many2many('project.tags', related='project_id.tag_ids', string=_('Tags'))
    order_line_ids = fields.One2many('tender.offer.line', 'tender_offer_id', string=_('Order Lines'))
    total_cost       = fields.Float(string=_('Total Cost'), compute='_compute_total_cost')
    total_lines_cost = fields.Float(string=_('Total Lines Cost'), store=True, copy=True, default=0.0)
    total_sell       = fields.Float(string=_('Total Selling Price'), store=True, copy=True, default=0.0)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string=_('Company'))
    currency_id = fields.Many2one('res.currency', string=_('Currency'))
    version_count = fields.Integer(string=_('Version'), compute='get_version_count')
    last_update_date = fields.Date(related='version_id.date', string=_('Last Update'))
    project_extra_expenses_ids = fields.One2many('project.extras', related='project_id.project_extras_ids')
    total_extra_cost = fields.Float(related='project_id.total_extra_cost', string=_('Total Extra Cost'))
    offer_total   = fields.Float(string=_('Total Cost'), compute='_compute_offer_total')
    profit_margin = fields.Float(string=_('Profit Margin %'), default=0.0,
                                  help='Applied to all lines - each line can be adjusted individually')
    overhead_percentage = fields.Float(
        string=_('Overhead %'), default=0.0, store=True, copy=True,
        help='نسبة الأوفر هيد محسوبة تلقائيًا = إجمالي الأوفر هيد (من شاشة '
             'الأوفر هيد بالمشروع) ÷ إجمالي تكلفة البنود بعد الهالك، '
             'وتوزع على البنود بالتناسب مع تكلفة كل بند.')
    project_overhead_ids = fields.One2many(
        'project.overhead.line', related='project_id.project_overhead_ids',
        string=_('Overhead Items'), readonly=False)
    total_overhead_amount = fields.Float(
        related='project_id.total_overhead_cost', string=_('Total Overhead Amount'))
    total_direct_cost = fields.Float(string=_('Total Direct Cost'), store=True, copy=True, default=0.0,
                                      help='إجمالي التكلفة المباشرة (التكلفة الأساسية + الهالك + حصة الأوفر هيد) لكل البنود.')
    down_payment = fields.Float(string=_("Down Payment"))
    down_payment_percentage = fields.Float(string=_("Down Payment Percentage"))
    top_sheet_id = fields.Many2one('top.sheet', string=_('Related Top Sheet'))
    project_duration_months = fields.Float(
        related='project_id.project_duration_months',
        string=_('Project Duration (Months)'),
        readonly=False,
        store=False,
    )

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
        for record in self:
            record.total_cost = sum(line.sub_total for line in record.order_line_ids)

    def _recompute_totals(self):
        """Call this after writing lines to keep totals in sync."""
        for record in self:
            record.total_lines_cost  = sum(line.cost_total for line in record.order_line_ids)
            record.total_direct_cost = sum(line.direct_cost_total for line in record.order_line_ids)
            record.total_sell        = sum(line.sub_total  for line in record.order_line_ids)

    def _recompute_direct_costs(self):
        """
        إعادة حساب التكلفة المباشرة (Direct Cost) لكل بند:
        1) تكلفة البند بعد الهالك = الكمية × تكلفة الأساس × (1 + نسبة الهالك%) — والهالك يُطبق على بنود
           الماتريال (flag = 'm') فقط، باقي البنود (عمالة/مصاريف/معدات/مقاولين) بدون هالك.
        2) إجمالي الأوفر هيد = إجمالي بنود شاشة الأوفر هيد بالمشروع (total_overhead_amount).
        3) نسبة الأوفر هيد % = إجمالي الأوفر هيد ÷ إجمالي تكلفة البنود بعد الهالك × 100 (تُحفظ للعرض فقط).
        4) حصة كل بند من الأوفر هيد = إجمالي الأوفر هيد × (تكلفة البند بعد الهالك ÷ إجمالي التكلفة بعد الهالك)
        5) التكلفة المباشرة الإجمالية للبند = تكلفته بعد الهالك + حصته من الأوفر هيد
        6) سعر البيع = التكلفة المباشرة للوحدة × (1 + نسبة الربح الخاصة بالبند%)
        """
        for offer in self:
            lines = offer.order_line_ids
            cost_after_wastage = {}
            total_after_wastage = 0.0
            for line in lines:
                wastage_pct = line.wastage_percentage if line.flag == 'm' else 0.0
                line_cost = line.qty * line.cost_price * (1 + wastage_pct / 100.0)
                cost_after_wastage[line] = line_cost
                total_after_wastage += line_cost

            overhead_total = offer.total_overhead_amount

            for line in lines:
                line_cost = cost_after_wastage.get(line, 0.0)
                if total_after_wastage:
                    line.overhead_share = overhead_total * (line_cost / total_after_wastage)
                else:
                    line.overhead_share = 0.0
                line.direct_cost_total = line_cost + line.overhead_share
                wastage_pct = line.wastage_percentage if line.flag == 'm' else 0.0
                if line.qty:
                    line.direct_cost_unit = line.direct_cost_total / line.qty
                else:
                    line.direct_cost_unit = line.cost_price * (1 + wastage_pct / 100.0)
                line.cost_total = line.qty * line.cost_price
                line.sell_price = line.direct_cost_unit * (1 + line.profit_margin_line / 100.0)
                line.sub_total = line.qty * line.sell_price

            if total_after_wastage:
                offer.overhead_percentage = overhead_total / total_after_wastage * 100.0
            else:
                offer.overhead_percentage = 0.0

    @api.onchange('project_overhead_ids', 'total_overhead_amount')
    def _onchange_total_overhead_amount(self):
        self._recompute_direct_costs()

    @api.onchange('profit_margin')
    def _onchange_profit_margin(self):
        for line in self.order_line_ids:
            line.profit_margin_line = self.profit_margin
        self._recompute_direct_costs()

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('_recomputing_totals'):
            self.with_context(_recomputing_totals=True)._recompute_totals()
        return res

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
                qty = version_line.qty
                cost_price = version_line.unit_price
                cost_total = qty * cost_price
                sell_price = cost_price
                sub_total = qty * sell_price
                order_lines.append((0, 0, {
                    'item_id': version_line.item_id.id,
                    'name': version_line.name,
                    'uom_id': version_line.uom_id.id,
                    'template_id': version_line.template_id.id,
                    'qty': qty,
                    'cost_price':         cost_price,
                    'wastage_percentage': 0.0,
                    'profit_margin_line': 0.0,
                    'sell_price':         sell_price,
                    'cost_total':         cost_total,
                    'sub_total':          sub_total,
                }))
            rec.order_line_ids = order_lines
            rec._recompute_direct_costs()

    @api.onchange('down_payment_percentage')
    def _onchange_down_payment_percentage(self):
        for rec in self:
            if rec.down_payment_percentage:
                total = rec.total_extra_cost + sum(line.sub_total for line in rec.order_line_ids)
                rec.down_payment = total * rec.down_payment_percentage

    @api.onchange('down_payment')
    def _onchange_down_payment(self):
        for rec in self:
            total = rec.total_extra_cost + sum(line.sub_total for line in rec.order_line_ids)
            if total and 0 < rec.down_payment <= total:
                rec.down_payment_percentage = rec.down_payment / total
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
    cost_price  = fields.Float(string=_('Cost Price'), store=True, copy=True, default=0.0)
    wastage_percentage = fields.Float(
        string=_('Wastage %'), default=0.0, store=True, copy=True,
        help='نسبة الهالك الخاصة بهذا البند — تُضاف على تكلفة الأساس ضمن التكلفة المباشرة.')
    overhead_share = fields.Float(
        string=_('Overhead Share'), store=True, copy=True, default=0.0,
        help='حصة هذا البند من الأوفر هيد على مستوى المشروع، موزعة بالتناسب مع تكلفته بعد الهالك.')
    direct_cost_unit = fields.Float(
        string=_('Direct Cost (Unit)'), store=True, copy=True, default=0.0,
        help='التكلفة المباشرة للوحدة = (تكلفة الأساس × (1 + نسبة الهالك%)) + حصة الوحدة من الأوفر هيد.')
    direct_cost_total = fields.Float(string=_('Direct Cost (Total)'), store=True, copy=True, default=0.0)
    profit_margin_line = fields.Float(
        string=_('Profit Margin %'), default=0.0, store=True, copy=True,
        help='نسبة الربح الخاصة بهذا البند، تُحسب على التكلفة المباشرة (Direct Cost) لا على تكلفة الأساس.')
    sell_price  = fields.Float(string=_('Selling Price'), store=True, copy=True)
    cost_total  = fields.Float(string=_('Total Cost'), store=True, copy=True)
    sub_total   = fields.Float(string=_('Subtotal'), store=True, copy=True)
    flag = fields.Selection(
        [('m', 'Material'), ('l', 'labour'), ('e', 'Expenses'), ('q', 'Equipment'), ('s', 'subcontractor')],
        string=_('Type'))
    company_id = fields.Many2one('res.company', related='tender_offer_id.company_id', string=_('Company'))
    currency_id = fields.Many2one('res.currency', related='tender_offer_id.currency_id', string=_('Currency'))
    template_id = fields.Many2one('tender.job.cost', string=_('Template'), domain="[('state', '=', 'approve')]")

    @api.onchange('qty', 'cost_price', 'wastage_percentage', 'profit_margin_line', 'flag')
    def _onchange_recompute_direct_cost(self):
        """إعادة حساب التكلفة المباشرة وسعر البيع لكل البنود عند تغيير
        الكمية أو تكلفة الأساس أو نسبة الهالك أو نسبة الربح أو نوع البند.
        نسبة الهالك تُطبق على بنود الماتريال (flag = 'm') فقط."""
        for rec in self:
            if rec.tender_offer_id:
                rec.tender_offer_id._recompute_direct_costs()
            else:
                wastage_pct = rec.wastage_percentage if rec.flag == 'm' else 0.0
                rec.cost_total = rec.qty * rec.cost_price
                direct_cost_unit = rec.cost_price * (1 + wastage_pct / 100.0)
                rec.direct_cost_unit = direct_cost_unit
                rec.direct_cost_total = rec.qty * direct_cost_unit
                rec.sell_price = direct_cost_unit * (1 + rec.profit_margin_line / 100.0)
                rec.sub_total = rec.qty * rec.sell_price

    @api.onchange('sell_price')
    def _onchange_sell_price_manual(self):
        """عند تعديل سعر البيع يدويًا، يُعاد حساب الإجمالي فقط."""
        for rec in self:
            rec.sub_total = rec.qty * rec.sell_price

    def write(self, vals):
        res = super().write(vals)
        cost_driving_fields = ('cost_price', 'qty', 'profit_margin_line', 'wastage_percentage', 'flag')
        if any(k in vals for k in cost_driving_fields) and not self.env.context.get('_recomputing_direct_costs'):
            offers = self.mapped('tender_offer_id')
            if offers:
                offers.with_context(_recomputing_direct_costs=True)._recompute_direct_costs()
        elif 'sell_price' in vals:
            for rec in self:
                rec.sub_total = rec.qty * rec.sell_price
        if any(k in vals for k in cost_driving_fields + ('sell_price',)):
            offers = self.mapped('tender_offer_id')
            if offers:
                offers.with_context(_recomputing_totals=True)._recompute_totals()
        return res

    @api.onchange('item_id')
    def _onchange_item_id(self):
        """Update the description and qty fields based on the selected item."""
        for rec in self:
            rec.name = rec.item_id.name
            rec.qty = 1.0
            rec.uom_id = rec.item_id.uom_id.id
