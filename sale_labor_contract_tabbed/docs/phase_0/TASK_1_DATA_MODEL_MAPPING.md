# Task 1: Data Model Mapping (Excel to Odoo Fields)

Date: 2026-03-18
Module: `sale_labor_contract_tabbed`
Scope: Map Excel columns to Odoo storage targets and classify fields as Input vs Computed.

## 1) Mapping Decision Summary

- **Employee Salary Details** values are stored on **Sale Order Lines** (`sale.order.line`) as float fields.
- **Government Fees** values are stored in a new **configuration model** (`labor.rules.config`) as float fields.
- Computed totals should be calculated primarily on `sale.order.line`, with optional aggregate totals on `sale.order`.

## 2) Header vs Line Ownership

### Line-level (`sale.order.line`) - Primary

Use line fields because each sold job is represented as a sales order line:

- `x_basic_salary` (Float)
- `x_housing_allowance` (Float)
- `x_transport_allowance` (Float)
- `x_food_allowance` (Float)

Recommended computed line totals:

- `x_salary_details_total` (Float, Computed)
  - Formula: `x_basic_salary + x_housing_allowance + x_transport_allowance + x_food_allowance`

Link each line to rules configuration:

- `x_labor_rules_config_id` (Many2one `labor.rules.config`)

Recommended computed fee total on `sale.order.line`:

- `x_government_fees_total` (Float, Computed)
  - Formula: `x_labor_rules_config_id.iqama_fee + x_labor_rules_config_id.work_permit_fee + x_labor_rules_config_id.visa_fee`

### Header-level (`sale.order`) - Secondary/Aggregate

Header fields are optional and should be used for aggregates only.

Example optional aggregates:

- `x_total_salary_details_all_lines` (Computed sum of line salary totals)
- `x_total_gov_fees_all_lines` (Computed sum of line government fee totals)

## 3) Government Fees Mapping

Create model: `labor.rules.config`

Suggested core fields:

- `name` (Char, required)
- `company_id` (Many2one `res.company`, default current company)
- `currency_id` (Many2one `res.currency`, related to company or explicit)
- `iqama_fee` (Float)
- `work_permit_fee` (Float)
- `visa_fee` (Float)
- `active` (Boolean, default True)

Link from `sale.order.line` to selected configuration:

- `x_labor_rules_config_id` (Many2one `labor.rules.config`)

## 4) Input vs Computed Classification

Managerial default policy:

- Fixed government and insurance fees are maintained by managers at configuration level.
- Business users should not directly edit these fixed fee values on `sale.order.line`.
- Lines consume these values as readonly related/computed fields.

### Input fields (User-entered)

- On `sale.order.line`:
  - `x_basic_salary`
  - `x_housing_allowance`
  - `x_transport_allowance`
  - `x_food_allowance`
  - `x_labor_rules_config_id` (selection of rule set; manager-only if policy requires locked defaults)

- On `labor.rules.config`:
  - `name`
  - `company_id`
  - `currency_id` (if not forced by company)
  - `iqama_fee` (manager-only edit)
  - `work_permit_fee` (manager-only edit)
  - `visa_fee` (manager-only edit)
  - `active`

### Computed fields (System-calculated)

- On `sale.order.line`:
  - `x_salary_details_total`
  - `x_government_fees_total`

Optional next computed aggregate:

- On `sale.order.line`:
  - `x_labor_contract_estimated_total` (Float, Computed)
  - Formula: `x_salary_details_total + x_government_fees_total`

## 5) Excel Column to Odoo Field Matrix

| Excel Section | Excel Column | Odoo Model | Odoo Field (Suggested) | Type | Ownership | Classification |
|---|---|---|---|---|---|---|
| Employee Salary Details | Basic | `sale.order.line` | `x_basic_salary` | Float | Line | Input |
| Employee Salary Details | Housing | `sale.order.line` | `x_housing_allowance` | Float | Line | Input |
| Employee Salary Details | Transport | `sale.order.line` | `x_transport_allowance` | Float | Line | Input |
| Employee Salary Details | Food | `sale.order.line` | `x_food_allowance` | Float | Line | Input |
| Government Fees | Iqama | `labor.rules.config` | `iqama_fee` | Float | Config | Input |
| Government Fees | Work Permit | `labor.rules.config` | `work_permit_fee` | Float | Config | Input |
| Government Fees | Visa | `labor.rules.config` | `visa_fee` | Float | Config | Input |

## 6) Notes for Implementation Phase

- Use `Monetary` instead of plain `Float` if currency-aware amounts are required in UI/reporting.
- Add `@api.depends(...)` on computed fields to ensure automatic recalculation.
- Add multi-company safety rules for `labor.rules.config` (`company_id` domain/filter).
- If fees should vary by nationality/job grade, extend `labor.rules.config` with those dimensions rather than storing duplicate values on each sale order.

---

Status: Investigation completed for Task 1 (line-level data model mapping and field classification).
