from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContractCompletionDeductionAllowance(models.Model):
    """ Model representing technical details for a project in the 'ProjectEngineerTechnical' module."""
    _name = 'contract.completion.deduction.allowance'
    _description = 'contract.completion.deduction.allowance'
    _rec_name = "name"

    name = fields.Char(string=_("Name"))
    item_id = fields.Many2one("tender.item", string=_("Item"))
    contract_type = fields.Selection([('owner', 'Owner'), ('subcontractor', 'Subcontractor')], readonly=True, string=_("Type Of Contract"))
    main_type = fields.Selection([('deduction', 'Deduction'), ('allowance', 'Allowance')], readonly=True, string=_("Main Type"))
    # account_id = fields.Many2one("account.account", string=_("Account"))
    calculation_type = fields.Selection([('percentage', 'Percentage'), ('amount', 'Amount')], string=_("Calculation Type"))
    percentage = fields.Float(string=_("Percentage"))
    amount = fields.Float(string=_("Amount"))
    request_id = fields.Many2one("project.completion.request", string=_("Completion Request"), ondelete="cascade")

    @api.constrains("percentage")
    def check_percentage(self):
        """Check that 'percentage' is not greater than or equal to 100."""
        if self.calculation_type == 'percentage' and self.percentage > 1:
            raise UserError("Percentage should be less than 100.")
        else:
            print("Right")
