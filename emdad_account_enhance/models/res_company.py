# -*- coding: utf-8 -*-
import re

from markupsafe import Markup

from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _emdad_remove_vat_number_text(self, text):
        vat_values = [vat for vat in (self.vat, self.partner_id.vat) if vat]
        patterns = [
            rf"\s*VAT Number\s*:\s*{re.escape(vat)}\s*(?:<br\s*/?>)?"
            for vat in vat_values
        ]
        patterns.append(r"\s*VAT Number\s*:\s*[A-Za-z0-9\-]{6,25}\s*(?:<br\s*/?>)?")
        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        return Markup(text)

    def _emdad_invoice_company_details_without_vat_number(self):
        self.ensure_one()
        return self._emdad_remove_vat_number_text(self.company_details or "")

    def _emdad_invoice_report_header_without_vat_number(self):
        self.ensure_one()
        return self._emdad_remove_vat_number_text(self.report_header or "")