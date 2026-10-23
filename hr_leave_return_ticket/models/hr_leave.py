from odoo import api, fields, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    # Yes / No instead of a checkbox: a mandatory checkbox could only be saved
    # when ticked, a Yes / No forces an explicit answer on every request.
    return_ticket_required = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is Return Ticket Required?",
        tracking=True,
    )
    return_ticket_file = fields.Binary(string="Upload Ticket", attachment=True)
    return_ticket_file_name = fields.Char(string="Ticket File Name")

    @api.onchange("return_ticket_required")
    def _onchange_return_ticket_required(self):
        if self.return_ticket_required != "yes":
            self.return_ticket_file = False
            self.return_ticket_file_name = False
