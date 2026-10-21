from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..models.document_common import DOC_FIELD_MAP


class HrEmployeeDocumentRenewal(models.TransientModel):
    _name = "hr.employee.document.renewal"
    _inherit = ["hr.employee.document.mixin"]
    _description = "Employee Document Renewal"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        employee = self.env["hr.employee"].browse(res.get("employee_id"))
        doc_type = res.get("doc_type")
        if employee and doc_type in DOC_FIELD_MAP:
            for generic, emp_field in DOC_FIELD_MAP[doc_type].items():
                if generic not in fields_list:
                    continue
                value = employee[emp_field]
                if isinstance(value, models.BaseModel):
                    value = value.id
                res[generic] = value
        return res

    @api.constrains("issue_date", "expiry_date")
    def _check_dates(self):
        for wiz in self:
            if wiz.issue_date and wiz.expiry_date and wiz.expiry_date < wiz.issue_date:
                raise ValidationError(_("Expiry date cannot be before the issue date."))

    def action_confirm(self):
        self.ensure_one()
        employee = self.employee_id
        mapping = DOC_FIELD_MAP[self.doc_type]

        old_issue_date = employee[mapping["issue_date"]]
        old_expiry_date = employee[mapping["expiry_date"]]

        employee_vals = {}
        history_vals = {
            "employee_id": employee.id,
            "doc_type": self.doc_type,
            "old_issue_date": old_issue_date,
            "old_expiry_date": old_expiry_date,
        }
        for generic, emp_field in mapping.items():
            value = self[generic]
            if isinstance(value, models.BaseModel):
                value = value.id
            employee_vals[emp_field] = value
            history_vals[generic] = value

        employee.write(employee_vals)
        self.env["hr.employee.document.history"].create(history_vals)
        return {"type": "ir.actions.act_window_close"}
