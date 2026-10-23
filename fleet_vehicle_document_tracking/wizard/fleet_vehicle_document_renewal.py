from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..models.document_common import DOC_FIELD_MAP


class FleetVehicleDocumentRenewal(models.TransientModel):
    _name = "fleet.vehicle.document.renewal"
    _inherit = ["fleet.vehicle.document.mixin"]
    _description = "Vehicle Document Renewal"

    vehicle_id = fields.Many2one("fleet.vehicle", string="Vehicle", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        vehicle = self.env["fleet.vehicle"].browse(res.get("vehicle_id"))
        doc_type = res.get("doc_type")
        if vehicle and doc_type in DOC_FIELD_MAP:
            for generic, field_name in DOC_FIELD_MAP[doc_type].items():
                if generic not in fields_list:
                    continue
                value = vehicle[field_name]
                if isinstance(value, models.BaseModel):
                    value = value.id
                res[generic] = value
            if "currency_id" in fields_list and vehicle.currency_id:
                res["currency_id"] = vehicle.currency_id.id
        return res

    @api.constrains("issue_date", "expiry_date")
    def _check_dates(self):
        for wiz in self:
            if wiz.issue_date and wiz.expiry_date and wiz.expiry_date < wiz.issue_date:
                raise ValidationError(_("Expiry date cannot be before the issue date."))

    def action_confirm(self):
        self.ensure_one()
        vehicle = self.vehicle_id
        mapping = DOC_FIELD_MAP[self.doc_type]
        History = self.env["fleet.vehicle.document.history"]

        history_vals = {
            "vehicle_id": vehicle.id,
            "doc_type": self.doc_type,
            "old_issue_date": vehicle[mapping["issue_date"]],
            "old_expiry_date": vehicle[mapping["expiry_date"]],
            "currency_id": self.currency_id.id,
        }
        vehicle_vals = {}
        for generic, field_name in mapping.items():
            value = self[generic]
            if isinstance(value, models.BaseModel):
                value = value.id
            vehicle_vals[field_name] = value
            history_vals[generic] = value

        if not History.search_count([("vehicle_id", "=", vehicle.id), ("doc_type", "=", self.doc_type)]):
            # nothing recorded yet for this document: this is its first entry
            history_vals["entry_type"] = "initial"
        vehicle.with_context(skip_initial_document_history=True).write(vehicle_vals)
        History.create(history_vals)
        # the document is renewed: close its pending renewal alerts
        vehicle._close_document_alerts(self.doc_type)
        return {"type": "ir.actions.act_window_close"}
