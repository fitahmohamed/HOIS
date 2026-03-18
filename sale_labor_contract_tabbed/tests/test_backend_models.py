from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLaborBackendModels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.partner = cls.env["res.partner"].create({"name": "Labor Test Partner"})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})

        cls.labor_product = cls.env["product.product"].create(
            {
                "name": "Labor Outsourcing",
                "type": "service",
                "list_price": 100.0,
                "x_is_labor_outsourcing": True,
            }
        )
        cls.normal_product = cls.env["product.product"].create(
            {
                "name": "Regular Product",
                "type": "service",
                "list_price": 50.0,
            }
        )

        cls.default_rules = cls.env["labor.rules.config"].sudo().create(
            {
                "name": "Default Rules",
                "company_id": cls.company.id,
                "is_default": True,
                "iqama_fee": 650.0,
                "work_permit_fee": 9700.0,
                "visa_fee": 2000.0,
                "exit_reentry_visa_fee": 200.0,
                "medical_insurance_fee": 1000.0,
            }
        )

    def _create_line(self, product, **extra_vals):
        vals = {
            "order_id": self.order.id,
            "product_id": product.id,
            "name": product.name,
            "product_uom_qty": 1.0,
            "product_uom_id": product.uom_id.id,
            "price_unit": product.list_price,
        }
        vals.update(extra_vals)
        return self.env["sale.order.line"].create(vals)

    def test_labor_line_computation_values(self):
        line = self._create_line(
            self.labor_product,
            x_labor_rules_config_id=self.default_rules.id,
            x_nationality="Saudi",
            x_basic_salary=2000.0,
            x_housing_allowance=1000.0,
            x_transport_allowance=500.0,
            x_food_allowance=300.0,
            x_other_allowances=200.0,
            x_contract_days=365.0,
            x_annual_leave_days=21.0,
            x_medical_exam_fee=100.0,
            x_service_fee=200.0,
        )

        self.assertTrue(line.x_is_labor_line)
        self.assertAlmostEqual(line.x_salary_details_total, 3800.0)
        self.assertAlmostEqual(line.x_total_salary, 4000.0)
        self.assertAlmostEqual(line.x_gosi_rate, 0.1175)
        self.assertAlmostEqual(line.x_gosi_amount, 352.5)
        self.assertAlmostEqual(line.x_government_fees_total, 12550.0)

        # Vacation: daily_rate × leave_days / 12
        expected_vacation = (4000.0 / 30.0) * (21.0 / 12.0)
        # EOS: total_salary / 2 (annual) / 12
        expected_eos = 4000.0 / 24.0
        self.assertAlmostEqual(line.x_vacation_accrual_monthly, expected_vacation, places=2)
        self.assertAlmostEqual(line.x_eos_accrual_monthly, expected_eos, places=2)

        expected_total_service_cost = (
            4000.0
            + 352.5
            + 1000.0
            + 100.0
            + 12550.0
            + expected_vacation
            + expected_eos
            + 0.0  # x_air_ticket_accrual_monthly
            + 0.0
            + 0.0
            + 200.0
        )
        self.assertAlmostEqual(line.x_total_service_cost, expected_total_service_cost, places=2)

    def test_recalculate_applies_default_rules(self):
        line = self._create_line(
            self.labor_product,
            x_nationality="مصري",
            x_basic_salary=1000.0,
            x_housing_allowance=500.0,
            x_transport_allowance=100.0,
            x_food_allowance=100.0,
        )
        self.assertFalse(line.x_labor_rules_config_id)

        self.order.action_recalculate_labor_costs()

        line = self.env["sale.order.line"].browse(line.id)
        self.assertEqual(line.x_labor_rules_config_id.id, self.default_rules.id)
        self.assertAlmostEqual(line.x_gosi_rate, 0.02)
        self.assertAlmostEqual(line.x_government_fees_total, 12550.0)

    def test_non_labor_line_stays_zero(self):
        line = self._create_line(
            self.normal_product,
            x_basic_salary=9999.0,
            x_housing_allowance=9999.0,
            x_labor_rules_config_id=self.default_rules.id,
        )
        self.assertFalse(line.x_is_labor_line)
        self.assertEqual(line.x_total_salary, 0.0)
        self.assertEqual(line.x_gosi_amount, 0.0)
        self.assertEqual(line.x_government_fees_total, 0.0)
        self.assertEqual(line.x_total_service_cost, 0.0)
