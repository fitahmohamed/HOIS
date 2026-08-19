# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class SubContractor(models.Model):
    _inherit = 'res.partner'

    is_subcontractor = fields.Boolean(string=_("Subcontractor"))

    def _can_create_vendor_subcontractor(self):
        return (
            self.env.user.has_group('nthub_constructions.construction_group_create_vendors_subcontractors')
            or self.env.user.has_group('base.group_system')
        )

    def _is_vendor_creation_request(self, vals):
        return (
            vals.get('supplier_rank', 0) > 0
            or self.env.context.get('default_supplier_rank', 0) > 0
            or self.env.context.get('res_partner_search_mode') == 'supplier'
        )

    def _is_subcontractor_creation_request(self, vals):
        return vals.get('is_subcontractor') or self.env.context.get('default_is_subcontractor')

    def _check_vendor_subcontractor_creation_access(self, vals):
        if (
                (self._is_vendor_creation_request(vals) or self._is_subcontractor_creation_request(vals))
                and not self._can_create_vendor_subcontractor()
        ):
            raise AccessError(_("Only authorized users can create vendors or subcontractors."))

    def _get_subcontractor_payable_account_id(self):
        account_id = self.env['ir.config_parameter'].sudo().get_param(
            'nthub_constructions.subcontractor_payable_account_id'
        )
        return int(account_id) if account_id else False

    def _apply_partner_defaults(self, vals):
        if self.env.context.get('default_is_subcontractor') and 'is_subcontractor' not in vals:
            vals['is_subcontractor'] = True
        if self.env.context.get('default_supplier_rank', 0) > 0 and not vals.get('supplier_rank'):
            vals['supplier_rank'] = self.env.context['default_supplier_rank']
        if vals.get('is_subcontractor') and not vals.get('property_account_payable_id'):
            account_id = self._get_subcontractor_payable_account_id()
            if account_id:
                vals['property_account_payable_id'] = account_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_vendor_subcontractor_creation_access(vals)
            self._apply_partner_defaults(vals)
        partners = super().create(vals_list)
        if not self._can_create_vendor_subcontractor():
            unauthorized_partners = partners.filtered(
                lambda partner: partner.supplier_rank > 0 or partner.is_subcontractor
            )
            if unauthorized_partners:
                raise AccessError(_("Only authorized users can create vendors or subcontractors."))
        return partners

    def write(self, vals):
        creates_vendor = vals.get('supplier_rank', 0) > 0
        creates_subcontractor = vals.get('is_subcontractor')
        if creates_vendor or creates_subcontractor:
            for partner in self:
                if (
                        (creates_vendor and not partner.supplier_rank)
                        or (creates_subcontractor and not partner.is_subcontractor)
                ):
                    partner._check_vendor_subcontractor_creation_access(vals)
        self._apply_partner_defaults(vals)
        return super().write(vals)

    def _increase_rank(self, field, n=1):
        if (
                field == 'supplier_rank'
                and n > 0
                and any(not partner.supplier_rank for partner in self)
                and not self._can_create_vendor_subcontractor()
        ):
            raise AccessError(_("Only authorized users can create vendors or subcontractors."))
        return super()._increase_rank(field, n)
