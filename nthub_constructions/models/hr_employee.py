from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    joining_date = fields.Date(
        string='Joining Date',
        copy=False,
        readonly=True,
        help='The first working day after the employee\'s approved leave.',
    )
class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def _action_validate(self, check_state=True):
        result = super()._action_validate(check_state)
        for leave in self.filtered(lambda leave: leave.employee_id and leave.date_to):
            leave.employee_id.current_version_id.joining_date = fields.Date.add(
                fields.Date.to_date(leave.date_to), days=1
            )
        return result
