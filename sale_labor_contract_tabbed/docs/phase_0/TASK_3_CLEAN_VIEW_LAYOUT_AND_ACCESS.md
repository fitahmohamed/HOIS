# Task 3: Clean View Layout and Access Permissions

Date: 2026-03-18
Module: `sale_labor_contract_tabbed`
Scope: Design a clean line-first layout (inside Sales Order Lines) and role-based visibility rules.

## 0) Correction from Client Discussion

The client sells the job itself as a Sales Order line, so the main data entry must be on `sale.order.line` (not only on `sale.order` header pages).

Target UX:

- Fields appear in the order line grid.
- Fields are available in the columns selector (the dots/options menu).
- Header pages are only for summary and configuration references.

## 1) Excel Columns Grouping into Logical Buckets (Line-Level)

Source columns were extracted from the workbook headers (notably row 4 and related notes).

### A) HR Bucket (Demographics)

Purpose: employee profile and contract context.

- `x_job_name` (Excel: اسم المهنة)
- `x_nationality` (Excel: الجنسية)
- `x_contract_type` (Excel: نوع العقد)
- `x_working_hours` (Excel: عدد ساعات العمل)

Optional HR-adjacent display fields:

- `x_annual_leave_days` (derived from contract policy: 21/30)
- `x_contract_days` (if captured directly)

### B) Finance Bucket (Salary / GOSI / Employee Entitlements)

Purpose: salary structure and statutory/accrual calculations.

Salary components:

- `x_basic_salary` (Excel: الراتب الاساسي)
- `x_housing_allowance` (Excel: بدل السكن)
- `x_transport_allowance` (Excel: بدل انتقال)
- `x_food_allowance` (Excel: بدل الطعام)
- `x_other_allowances` (Excel: بدلات اخري)
- `x_total_salary` (Excel: اجمالي الراتب)

GOSI:

- `x_gosi_amount` (computed)
- `x_gosi_rate` (computed or helper display)

Employee entitlements:

- `x_vacation_accrual_monthly` (computed)
- `x_eos_accrual_monthly` (computed)
- `x_air_ticket_accrual_monthly` (computed/manual by policy)
- `x_employee_entitlements_total` (computed)

### C) Ops Bucket (Service Fees / Government / Operational Costs)

Purpose: operational and pass-through cost components.

Service and operational fees:

- `x_service_fee` (Excel: رسوم الخدمة)
- `x_medical_insurance_fee` (Excel: تامين طبي)
- `x_medical_exam_fee` (Excel: فحص طبي)
- `x_municipality_card_fee` (Excel: كرت البلدية)
- `x_linkage_ajeer_fee` (Excel: رسوم تحويل + ربط اجير)

Government fees (typically from config):

- `x_labor_rules_config_id` (M2O)
- `x_iqama_fee` (related/display)
- `x_work_permit_fee` (related/display)
- `x_visa_or_transfer_fee` (related/display)
- `x_exit_reentry_visa_fee` (related/display)
- `x_government_fees_total` (computed)

Top-level ops aggregate:

- `x_total_service_cost` (computed: all monthly costs + service fee)

## 2) Technical IDs for User Groups

Use module namespace prefix: `sale_labor_contract_tabbed`.

Recommended group IDs:

- `group_recruitment_hr`
  - HR team can edit demographics and contract context.
- `group_recruitment_finance`
  - Finance team can edit salary/fee numbers and see all computed totals.
- `group_recruitment_ops`
  - Operations team can edit service and government fee operational fields.
- `group_recruitment_manager`
  - Full access across all pages and approval-level controls.

XML record skeleton (security groups):

```xml
<record id="group_recruitment_hr" model="res.groups">
    <field name="name">Recruitment - HR</field>
    <field name="category_id" ref="base.module_category_sales_management"/>
</record>

<record id="group_recruitment_finance" model="res.groups">
    <field name="name">Recruitment - Finance</field>
    <field name="category_id" ref="base.module_category_sales_management"/>
</record>

<record id="group_recruitment_ops" model="res.groups">
    <field name="name">Recruitment - Operations</field>
    <field name="category_id" ref="base.module_category_sales_management"/>
</record>

<record id="group_recruitment_manager" model="res.groups">
    <field name="name">Recruitment - Manager</field>
    <field name="implied_ids" eval="[(4, ref('sale_labor_contract_tabbed.group_recruitment_hr')), (4, ref('sale_labor_contract_tabbed.group_recruitment_finance')), (4, ref('sale_labor_contract_tabbed.group_recruitment_ops'))]"/>
    <field name="category_id" ref="base.module_category_sales_management"/>
</record>
```

Access intent matrix:

- HR: read/write HR line columns.
- Finance: read/write Finance line columns and computed visibility.
- Ops: read/write operational non-fixed columns only.
- Manager: full read/write all line columns, defaults, and fixed fees.

Managerial policy for fixed fees:

- Government and fixed insurance fees are defaulted from managerial configuration.
- Non-manager users can view these values but cannot edit them.
- Only `group_recruitment_manager` can create/update fee defaults in `labor.rules.config` and override fixed fee values on lines.

## 3) Odoo XML Layout Sketch (Sale Order Line + Dots Menu)

Main point: fields must be added to the `order_line` tree so users can show/hide them from the dots column picker.

Important technical note:

- Odoo optional columns menu is a flat list; it does not render section headers/groups by default.
- Practical workaround is naming labels with prefixes like `HR -`, `FIN -`, `OPS -` and placing fields in ordered blocks.

Example tree extension (inside `sale.order` form, `order_line` one2many tree):

```xml
<xpath expr="//field[@name='order_line']/tree//field[@name='discount']" position="after">
    <!-- HR block -->
    <field name="x_job_name" string="HR - Job" optional="hide" groups="sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_nationality" string="HR - Nationality" optional="hide" groups="sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_contract_type" string="HR - Contract Type" optional="hide" groups="sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_working_hours" string="HR - Working Hours" optional="hide" groups="sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager"/>

    <!-- FIN block -->
    <field name="x_basic_salary" string="FIN - Basic" optional="hide" groups="sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_housing_allowance" string="FIN - Housing" optional="hide" groups="sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_transport_allowance" string="FIN - Transport" optional="hide" groups="sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_food_allowance" string="FIN - Food" optional="hide" groups="sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_total_salary" string="FIN - Total Salary" optional="show" readonly="1" groups="sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_gosi_amount" string="FIN - GOSI" optional="show" readonly="1" groups="sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_manager"/>

    <!-- OPS block -->
    <field name="x_service_fee" string="OPS - Service Fee" optional="show" groups="sale_labor_contract_tabbed.group_recruitment_ops,sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager" readonly="1"/>
    <field name="x_labor_rules_config_id" string="OPS - Rules Config" optional="hide" groups="sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_government_fees_total" string="OPS - Gov Fees" optional="show" readonly="1" groups="sale_labor_contract_tabbed.group_recruitment_ops,sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_medical_insurance_fee" string="OPS - Medical Insurance" optional="show" readonly="1" groups="sale_labor_contract_tabbed.group_recruitment_ops,sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_iqama_fee" string="OPS - Iqama" optional="hide" readonly="1" groups="sale_labor_contract_tabbed.group_recruitment_ops,sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_work_permit_fee" string="OPS - Work Permit" optional="hide" readonly="1" groups="sale_labor_contract_tabbed.group_recruitment_ops,sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_visa_or_transfer_fee" string="OPS - Visa/Transfer" optional="hide" readonly="1" groups="sale_labor_contract_tabbed.group_recruitment_ops,sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_hr,sale_labor_contract_tabbed.group_recruitment_manager"/>
    <field name="x_total_service_cost" string="OPS - Total Service Cost" optional="show" readonly="1" groups="sale_labor_contract_tabbed.group_recruitment_manager,sale_labor_contract_tabbed.group_recruitment_finance,sale_labor_contract_tabbed.group_recruitment_ops"/>
</xpath>
```

  Manager-only edit pattern:

  - Keep fee source fields editable in `labor.rules.config` with manager ACL only.
  - On `sale.order.line`, expose fee fields as computed/related readonly values for all users.
  - If a temporary manual override is required, add dedicated override fields with `groups="sale_labor_contract_tabbed.group_recruitment_manager"`.

Recommended companion pages:

- Keep a slim header notebook on `sale.order` for read-only summaries and diagnostics.
- Keep detailed editable business fields primarily on `sale.order.line`.

## 4) Visibility and Editability Strategy

- Use `groups` at field level in line tree for role-based visibility inside the dots menu.
- Use `optional="show|hide"` to control default visible columns.
- Keep fixed insurance/government fees readonly and computed/related on `sale.order.line`.
- Keep high-risk totals readonly and computed in Python on `sale.order.line`.
- Expose only safe aggregates on header pages for quick review.

## 5) Implementation Notes

- Final field names should align with actual model fields to avoid XML parse errors.
- For many hidden technical columns, consider creating a dedicated line form view (opened from line) in addition to tree columns.
- If two teams can view but only one can edit, combine `groups` with conditional `readonly` logic.
- Add matching ACL entries in `security/ir.model.access.csv` for any new config models.
- If you need true visual grouping inside the column chooser itself, it requires web client customization; standard Odoo list optional picker is flat.

---

Status: Clean line-level view and permission design completed for implementation.
