from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    vs_po_contract_ref = fields.Char(
        string="PO/Contract Ref.",
        copy=True,
        tracking=True,
    )
    vs_invoice_payment_status = fields.Selection(
        [
            ("no_invoice", "No Invoice"),
            ("not_paid", "Not Paid"),
            ("in_payment", "In Payment"),
            ("partial", "Partially Paid"),
            ("paid", "Paid"),
            ("reversed", "Reversed"),
        ],
        string="Invoice Payment Status",
        compute="_compute_vs_invoice_payment_status",
        store=True,
    )
    vs_site_no_id = fields.Many2one(
        "account.analytic.account",
        string="Site No",
        compute="_compute_vs_analytic_summary",
        store=True,
    )
    vs_department_id = fields.Many2one(
        "account.analytic.account",
        string="Department",
        compute="_compute_vs_analytic_summary",
        store=True,
    )
    vs_truck_id = fields.Many2one(
        "account.analytic.account",
        string="Truck",
        compute="_compute_vs_analytic_summary",
        store=True,
    )
    vs_truck_ids = fields.Many2many(
        "account.analytic.account",
        "sale_order_truck_rel",
        "order_id",
        "account_id",
        string="Trucks",
        compute="_compute_vs_truck_ids",
        store=True,
    )

    @api.constrains("state", "vs_po_contract_ref")
    def _check_vs_po_contract_ref(self):
        if self.env.context.get("skip_vs_po_contract_ref_required"):
            return
        for order in self:
            if order.state != "cancel" and not order.vs_po_contract_ref:
                raise ValidationError(_("PO/Contract Ref. is required."))
                    
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.setdefault("vs_po_contract_ref", self.vs_po_contract_ref)
        return super(SaleOrder, self.with_context(skip_vs_po_contract_ref_required=True)).copy(default)

    @api.depends("invoice_ids.state", "invoice_ids.move_type", "invoice_ids.payment_state")
    def _compute_vs_invoice_payment_status(self):
        for order in self:
            invoices = order.invoice_ids.filtered(
                lambda move: move.state == "posted" and move.move_type in ("out_invoice", "out_refund")
            )
            if not invoices:
                order.vs_invoice_payment_status = "no_invoice"
                continue

            states = set(invoices.mapped("payment_state"))
            if states == {"reversed"}:
                order.vs_invoice_payment_status = "reversed"
            elif states <= {"paid", "reversed"}:
                order.vs_invoice_payment_status = "paid"
            elif "partial" in states or ("paid" in states and states - {"paid", "reversed"}):
                order.vs_invoice_payment_status = "partial"
            elif "in_payment" in states:
                order.vs_invoice_payment_status = "in_payment"
            else:
                order.vs_invoice_payment_status = "not_paid"

    @api.depends("order_line.display_type", "order_line.analytic_distribution")
    def _compute_vs_analytic_summary(self):
        site_plan = self.env["sale.order.line"]._vs_get_plan_by_name(["site no", "site", "site number"])
        department_plan = self.env["sale.order.line"]._vs_get_plan_by_name(["department"])
        truck_plan = self.env["sale.order.line"]._vs_get_plan_by_name(["truck"])
        for order in self:
            lines = order.order_line.filtered(lambda line: not line.display_type)
            site_ids = list({
                line._vs_get_analytic_account_value(site_plan).id
                for line in lines
                if line._vs_get_analytic_account_value(site_plan)
            })
            department_ids = list({
                line._vs_get_analytic_account_value(department_plan).id
                for line in lines
                if line._vs_get_analytic_account_value(department_plan)
            })
            truck_ids = list({
                line._vs_get_analytic_account_value(truck_plan).id
                for line in lines
                if line._vs_get_analytic_account_value(truck_plan)
            })
            order.vs_site_no_id = site_ids[0] if len(site_ids) == 1 else False
            order.vs_department_id = department_ids[0] if len(department_ids) == 1 else False
            order.vs_truck_id = truck_ids[0] if len(truck_ids) == 1 else False
    
    @api.depends("order_line.display_type", "order_line.analytic_distribution")
    def _compute_vs_truck_ids(self):
        truck_plan = self.env["sale.order.line"]._vs_get_plan_by_name(["truck"])
        for order in self:
            lines = order.order_line.filtered(lambda line: not line.display_type)
            truck_ids = list({
                line._vs_get_analytic_account_value(truck_plan).id
                for line in lines
                if line._vs_get_analytic_account_value(truck_plan)
                and line._vs_get_analytic_account_value(truck_plan).exists()
            })
            order.vs_truck_ids = [(6, 0, truck_ids)]


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.constrains("display_type", "is_downpayment", "analytic_distribution")
    def _check_vs_analytic_distribution_required(self):
        for line in self:
            if not line.display_type and not line.is_downpayment and not line.analytic_distribution:
                raise ValidationError(_("Analytic Distribution is required on sales order lines."))

    @api.model
    def _vs_get_plan_by_name(self, names):
        domain = ["|"] * (len(names) - 1)
        for name in names:
            domain.append(("name", "ilike", name))
        return self.env["account.analytic.plan"].search(domain + [("parent_id", "=", False)], limit=1)

    def _vs_get_distribution_account_for_plan(self, plan):
        self.ensure_one()
        if not plan or not self.analytic_distribution:
            return False
        for account_key in self.analytic_distribution:
            account_ids = [int(account_id) for account_id in account_key.split(",") if account_id]
            account = self.env["account.analytic.account"].browse(account_ids).filtered(
                lambda analytic_account: analytic_account.root_plan_id == plan
            )[:1]
            if account:
                return account
        return False

    def _vs_get_analytic_account_value(self, plan):
        self.ensure_one()
        if not plan:
            return False
        column_name = plan._column_name()
        if column_name in self._fields:
            account = self[column_name]
            if account:
                return account
        return self._vs_get_distribution_account_for_plan(plan)