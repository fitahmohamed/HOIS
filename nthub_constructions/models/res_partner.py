from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_internal_employee = fields.Boolean(
        string='Internal Employee',
        compute='_compute_is_internal_employee',
        store=True,
        index=True,
    )

    @api.depends('employee_ids')
    def _compute_is_internal_employee(self):
        for partner in self:
            partner.is_internal_employee = bool(
                partner.with_context(active_test=False).employee_ids
            )

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = list(domain or [])
        if not self.env.context.get('include_employee_partners'):
            domain = fields.Domain.AND([
                domain,
                [('is_internal_employee', '=', False)],
            ])
        return super().name_search(name=name, domain=domain, operator=operator, limit=limit)