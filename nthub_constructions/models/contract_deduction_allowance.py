from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContractDeductionAllowance(models.Model):
    """ Model representing technical details for a project in the 'ProjectEngineerTechnical' module."""
    _name = 'contract.deduction.allowance'
    _description = 'contract.deduction.allowance'
    _rec_name = "name"

    name = fields.Char(string=_("Name"))
    item_id = fields.Many2one("tender.item", string=_("Item"))
    contract_type = fields.Selection([('owner', 'Owner'), ('subcontractor', 'Subcontractor')], readonly=True, string=_("Type Of Contract"))
    main_type = fields.Selection([('deduction', 'Deduction'), ('allowance', 'Allowance')], readonly=True, string=_("Main Type"))
    # account_id = fields.Many2one("account.account", string=_("Account"))
    calculation_type = fields.Selection([('percentage', 'Percentage'), ('amount', 'Amount')], string=_("Calculation Type"))
    percentage = fields.Float(string=_("Percentage"))
    amount = fields.Float(string=_("Amount"))
    contract_id = fields.Many2one("owner.contract", string=_("Contract"), ondelete='cascade')

    @api.constrains("percentage")
    def check_percentage(self):
        """Check that 'percentage' is not greater than or equal to 100."""
        if self.calculation_type == 'percentage' and self.percentage > 1:
            raise UserError("Percentage should be less than 100.")
        else:
            print("Right")

    @api.onchange("amount")
    def clac_dedct_perc(self):
        """Calculate the deduction percentage based on the entered amount."""
        if self.main_type == 'deduction':
            item_tot = 0
            item_line = self.contract_id.owner_contract_line_ids.filtered(lambda x: x.item_id == self.item_id)
            if item_line:
                for item in item_line:
                    item_tot += item.amount
            if item_tot > 0:
                self.percentage = (self.amount / item_tot)

