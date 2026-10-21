from odoo import api, fields, models

from .document_common import STATUS_SELECTION, get_status


class HrEmployeeDocumentHistory(models.Model):
    _name = "hr.employee.document.history"
    _inherit = ["hr.employee.document.mixin"]
    _description = "Employee Document Renewal History"
    _order = "renewal_date desc, id desc"
    _rec_name = "doc_type"

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="employee_id.company_id", store=True)
    renewal_date = fields.Datetime(
        string="Renewal Date", default=fields.Datetime.now, required=True
    )
    user_id = fields.Many2one(
        "res.users", string="Renewed By", default=lambda self: self.env.user, required=True
    )
    old_issue_date = fields.Date(string="Old Issue Date")
    old_expiry_date = fields.Date(string="Old Expiry Date")
    # issue_date / expiry_date (from the mixin) hold the NEW values
    issue_date = fields.Date(string="New Issue Date")
    expiry_date = fields.Date(string="New Expiry Date")
    # automatic, based on the new expiry date and the renewal_tracker settings
    status = fields.Selection(
        STATUS_SELECTION, string="Status", compute="_compute_status", store=True, index=True
    )

    @api.depends("expiry_date")
    def _compute_status(self):
        settings = self.env["renewal.settings"].sudo()._get_settings()
        today = fields.Date.today()
        for rec in self:
            rec.status = get_status(rec.expiry_date, settings, today)

    @api.model
    def _recompute_document_status(self):
        records = self.sudo().search([("expiry_date", "!=", False)])
        self.env.add_to_compute(self._fields["status"], records)
        records._recompute_recordset(["status"])
