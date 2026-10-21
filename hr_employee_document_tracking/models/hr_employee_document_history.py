from odoo import fields, models


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
