from odoo import api, fields, models, _


class NewVersionWizard(models.TransientModel):
    _name = 'new.version.wizard'
    _description = 'New Version Wizard'

    version_id = fields.Many2one('tender.offer.version', string=_('Select Version'), required=True, domain="[('tender_offer_id', '=', tender_offer_id),('state', '=', 'confirm')]")
    tender_offer_id = fields.Many2one('tender.offer', string=_('Tender Offer'))
    description = fields.Char(string=_('Description'), related='version_id.description')

    def confirm(self):
        order_lines = []
        version = self.env['tender.offer.version'].search([('id', '=', self.version_id.id)])
        for rec in version:
            for line in rec.version_line_ids:
                order_lines.append((0, 0, {
                    'item_id': line.item_id.id,
                    'name': line.name,
                    'uom_id': line.uom_id.id,
                    'template_id': line.template_id.id,
                    'qty': line.qty,
                    'unit_price': line.unit_price,
                }))
            version_order = self.env['tender.offer.version'].create({
                'customer_id': rec.customer_id.id,
                'project_id': rec.project_id.id,
                'tender_offer_id': rec.tender_offer_id.id,
                'date': fields.Datetime.now(),
                'version_line_ids': order_lines
            })
        #     offer = self.env['tender.offer'].search([('id', '=', self.tender_offer_id.id)])
        #     offer.update({
        #         'version_id': version_order.id,
        #     })
        # offer = offer.onchange_version_id()
        form_view_id = self.env.ref("nthub_constructions_tenders.tender_version_view_form").id
        return {
            'type': 'ir.actions.act_window',
            'name': _('version'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tender.offer.version',
            'views': [(form_view_id, 'form')],
            'target': 'current',
            'domain': [('id', '=', version_order.id)],
            'res_id': version_order.id

        }


