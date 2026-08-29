from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SubTaskWizard(models.TransientModel):
    _name = 'sub.task.wizard'
    _description = 'Sub Task Wizard'

    project_sub_task_id = fields.Many2one('project.task')
    product_sub_task_ids = fields.One2many('product.transfer.wizard', 'sub_task_wizard_id', string=_('Products'))
    product_ids = fields.Many2many("product.product", compute='compute_product_available')

    @api.depends('product_sub_task_ids', 'product_sub_task_ids.product_id')
    def compute_product_available(self):
        """ Set domain on products records."""
        for rec in self:
            rec.project_sub_task_id = self.env.context.get('active_id')
            domain_product_records = rec.project_sub_task_id.product_sub_task_ids.filtered(
                lambda l: l.product_id.type in ['product', 'consu'] and l.remaining > 0).mapped('product_id')
            rec.product_ids = domain_product_records

    def create_stock_picking(self):
        """ Create Stock Picking. """
        source = int(self.env['ir.config_parameter'].sudo().get_param('nthub_constructions.source_location_id'))
        if not source:
            raise UserError(_("Please configure source location in Settings."))

        stock_picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.project_sub_task_id.picking_type_id.id,
            'location_id': source,
            'location_dest_id': self.project_sub_task_id.location_dest_id.id,
            'project_task_id': self.project_sub_task_id.id,
            'move_ids_without_package': [(0, 0, {
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'location_id': source,
                'location_dest_id': self.project_sub_task_id.location_dest_id.id,
                'product_uom_qty': line.quantity_product,
            }) for line in self.product_sub_task_ids]
        })
        stock_picking.action_confirm()
        stock_picking.button_validate()
        for p in self.product_sub_task_ids:
            product_line = self.project_sub_task_id.product_sub_task_ids.filtered(
                lambda l: l.product_id == p.product_id)
            product_line.remaining -= p.quantity_product

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'res_id': stock_picking.id,
            'domain': [('project_task_id', '=', self.project_sub_task_id.id)],
            'target': 'current',
        }


class ProductTransferWizard(models.TransientModel):
    _name = 'product.transfer.wizard'
    _description = 'Product Transfer'

    sub_task_wizard_id = fields.Many2one("sub.task.wizard", string=_("Project Task"))
    product_id = fields.Many2one("product.product", string=_("Product"))
    quantity_product = fields.Float(string=_("Quantity"))
    product_ids = fields.Many2many("product.product", related='sub_task_wizard_id.product_ids')
