from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_job_name = fields.Char(string="Job Name")
    x_nationality = fields.Char(string="Nationality")
    x_contract_type = fields.Selection(
        [("single", "Single"), ("family", "Family")],
        string="Contract Type",
    )
    x_working_hours = fields.Float(string="Working Hours")
    x_contract_days = fields.Float(string="Contract Days", default=365.0)
    x_annual_leave_days = fields.Float(string="Annual Leave Days")

    x_basic_salary = fields.Monetary(currency_field="currency_id")
    x_housing_allowance = fields.Monetary(currency_field="currency_id")
    x_transport_allowance = fields.Monetary(currency_field="currency_id")
    x_food_allowance = fields.Monetary(currency_field="currency_id")
    x_other_allowances = fields.Monetary(currency_field="currency_id")

    x_salary_details_total = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_x_salary_details_total",
        store=True,
    )
    x_total_salary = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_x_total_salary",
        store=True,
    )

    x_gosi_rate = fields.Float(compute="_compute_x_gosi_rate_amount", store=True)
    x_gosi_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_x_gosi_rate_amount",
        store=True,
    )

    x_labor_rules_config_id = fields.Many2one(
        "labor.rules.config",
        string="Labor Rules Config",
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )

    x_iqama_fee = fields.Monetary(
        related="x_labor_rules_config_id.iqama_fee",
        currency_field="currency_id",
        readonly=True,
        store=True,
    )
    x_work_permit_fee = fields.Monetary(
        related="x_labor_rules_config_id.work_permit_fee",
        currency_field="currency_id",
        readonly=True,
        store=True,
    )
    x_visa_or_transfer_fee = fields.Monetary(
        related="x_labor_rules_config_id.visa_fee",
        currency_field="currency_id",
        readonly=True,
        store=True,
    )
    x_exit_reentry_visa_fee = fields.Monetary(
        related="x_labor_rules_config_id.exit_reentry_visa_fee",
        currency_field="currency_id",
        readonly=True,
        store=True,
    )
    x_medical_insurance_fee = fields.Monetary(
        related="x_labor_rules_config_id.medical_insurance_fee",
        currency_field="currency_id",
        readonly=True,
        store=True,
    )

    x_medical_exam_fee = fields.Monetary(currency_field="currency_id")
    x_municipality_card_fee = fields.Monetary(currency_field="currency_id")
    x_linkage_ajeer_fee = fields.Monetary(currency_field="currency_id")
    x_service_fee = fields.Monetary(currency_field="currency_id")

    x_government_fees_total = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_x_government_fees_total",
        store=True,
    )

    x_vacation_accrual_monthly = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_x_vacation_accrual_monthly",
        store=True,
    )
    x_eos_accrual_monthly = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_x_eos_accrual_monthly",
        store=True,
    )
    x_air_ticket_accrual_monthly = fields.Monetary(currency_field="currency_id")

    x_total_service_cost = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_x_total_service_cost",
        store=True,
    )

    x_is_labor_line = fields.Boolean(
        compute="_compute_x_is_labor_line",
        store=True,
    )

    @api.depends("product_id", "product_id.product_tmpl_id.x_is_labor_outsourcing")
    def _compute_x_is_labor_line(self):
        for line in self:
            line.x_is_labor_line = bool(
                line.product_id and line.product_id.product_tmpl_id.x_is_labor_outsourcing
            )

    @api.onchange("product_id")
    def _onchange_product_id_x_labor_defaults(self):
        for line in self:
            if line.x_is_labor_line:
                line._apply_labor_defaults(force=False)

    def _apply_labor_defaults(self, force=False):
        for line in self:
            if not line.x_is_labor_line:
                continue
            if line.x_labor_rules_config_id and not force:
                continue
            company = line.company_id or line.order_id.company_id or self.env.company
            default_cfg = self.env["labor.rules.config"]._default_for_company(self.env, company)
            if default_cfg:
                line.x_labor_rules_config_id = default_cfg

    def _recompute_labor_fields(self):
        self._compute_x_salary_details_total()
        self._compute_x_total_salary()
        self._compute_x_gosi_rate_amount()
        self._compute_x_government_fees_total()
        self._compute_x_vacation_accrual_monthly()
        self._compute_x_eos_accrual_monthly()
        self._compute_x_total_service_cost()

    @api.depends(
        "x_basic_salary",
        "x_housing_allowance",
        "x_transport_allowance",
        "x_food_allowance",
    )
    def _compute_x_salary_details_total(self):
        for line in self:
            if not line.x_is_labor_line:
                line.x_salary_details_total = 0.0
                continue
            line.x_salary_details_total = (
                line.x_basic_salary
                + line.x_housing_allowance
                + line.x_transport_allowance
                + line.x_food_allowance
            )

    @api.depends(
        "x_basic_salary",
        "x_housing_allowance",
        "x_transport_allowance",
        "x_food_allowance",
        "x_other_allowances",
    )
    def _compute_x_total_salary(self):
        for line in self:
            if not line.x_is_labor_line:
                line.x_total_salary = 0.0
                continue
            line.x_total_salary = (
                line.x_basic_salary
                + line.x_housing_allowance
                + line.x_transport_allowance
                + line.x_food_allowance
                + line.x_other_allowances
            )

    @api.depends("x_basic_salary", "x_housing_allowance", "x_nationality")
    def _compute_x_gosi_rate_amount(self):
        for line in self:
            if not line.x_is_labor_line:
                line.x_gosi_rate = 0.0
                line.x_gosi_amount = 0.0
                continue

            nationality = (line.x_nationality or "").strip().lower()
            saudi_aliases = {"saudi", "sa", "ksa", "saudi arabia", "سعودي", "السعودية"}
            line.x_gosi_rate = 0.1175 if nationality in saudi_aliases else 0.02
            line.x_gosi_amount = (line.x_basic_salary + line.x_housing_allowance) * line.x_gosi_rate

    @api.depends(
        "x_iqama_fee",
        "x_work_permit_fee",
        "x_visa_or_transfer_fee",
        "x_exit_reentry_visa_fee",
    )
    def _compute_x_government_fees_total(self):
        for line in self:
            if not line.x_is_labor_line:
                line.x_government_fees_total = 0.0
                continue
            line.x_government_fees_total = (
                line.x_iqama_fee
                + line.x_work_permit_fee
                + line.x_visa_or_transfer_fee
                + line.x_exit_reentry_visa_fee
            )

    @api.depends("x_total_salary", "x_annual_leave_days")
    def _compute_x_vacation_accrual_monthly(self):
        for line in self:
            if not line.x_is_labor_line:
                line.x_vacation_accrual_monthly = 0.0
                continue
            line.x_vacation_accrual_monthly = (line.x_total_salary / 30.0) * (line.x_annual_leave_days / 12.0)

    @api.depends("x_total_salary")
    def _compute_x_eos_accrual_monthly(self):
        for line in self:
            if not line.x_is_labor_line:
                line.x_eos_accrual_monthly = 0.0
                continue
            line.x_eos_accrual_monthly = line.x_total_salary / 24.0

    @api.depends(
        "x_total_salary",
        "x_gosi_amount",
        "x_medical_insurance_fee",
        "x_medical_exam_fee",
        "x_government_fees_total",
        "x_vacation_accrual_monthly",
        "x_eos_accrual_monthly",
        "x_air_ticket_accrual_monthly",
        "x_municipality_card_fee",
        "x_linkage_ajeer_fee",
        "x_service_fee",
    )
    def _compute_x_total_service_cost(self):
        for line in self:
            if not line.x_is_labor_line:
                line.x_total_service_cost = 0.0
                continue
            monthly_costs = (
                line.x_total_salary
                + line.x_gosi_amount
                + line.x_medical_insurance_fee
                + line.x_medical_exam_fee
                + line.x_government_fees_total
                + line.x_vacation_accrual_monthly
                + line.x_eos_accrual_monthly
                + line.x_air_ticket_accrual_monthly
                + line.x_municipality_card_fee
                + line.x_linkage_ajeer_fee
            )
            line.x_total_service_cost = monthly_costs + line.x_service_fee
            line.price_unit = line.x_total_service_cost
