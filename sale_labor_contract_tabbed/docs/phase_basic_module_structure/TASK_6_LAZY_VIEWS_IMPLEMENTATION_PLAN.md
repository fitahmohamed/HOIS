# Task 6: Lazy Views Implementation Plan (Step-by-Step with Upgrade + Logs)

Date: 2026-03-18
Module: sale_labor_contract_tabbed
Goal: Add views gradually with low risk. After every small step, upgrade module and validate logs before continuing.

## 0) Upgrade and Log Baseline (Use After Every Step)

Run this command after each step:

```powershell
d:/odoo/odoo19/.venv/Scripts/python.exe d:/odoo/odoo19/odoo19/odoo-bin -c d:/odoo/odoo19/odoo_conf/odoo19.conf -d odoo19_dev -u sale_labor_contract_tabbed --stop-after-init --log-level=info
```

Pass criteria each time:

- No traceback in logs.
- Module sale_labor_contract_tabbed loaded successfully.
- Registry loaded successfully.
- No XML parse errors.

If fail:

1. Fix only the last step changes.
2. Re-run same upgrade command.
3. Continue only after pass.

## 1) Step 1 - Minimal View Scaffolding Only

Scope:

- Create views folder and base files with only safe inherited records:
  - views/product_template_views.xml
  - views/sale_order_views.xml
  - views/sale_order_line_views.xml
  - views/labor_rules_config_views.xml

Implementation:

- Add empty/safe inherited views with valid model, inherit_id, and xpath placeholders.
- Do not add new fields to UI yet.
- Add these files to manifest data list.

Upgrade + logs:

- Run baseline command.
- Confirm module loads with no XML errors.

## 2) Step 2 - Product Trigger Field View

Scope:

- Inherit product template form view.
- Show field: x_is_labor_outsourcing.

Implementation:

- Add field in a small, stable area (sales tab or general section).
- Keep this step isolated (product view only).

Upgrade + logs:

- Run baseline command.
- In UI confirm product form opens and field displays.

## 3) Step 3 - Config Model Views + Menu (Manager First)

Scope:

- Create tree and form for labor.rules.config.
- Add menu and action under Sales configuration.

Implementation:

- Form fields: name, company_id, is_default, active, fee fields.
- Initially restrict menu/action with base.group_system (temporary safe lock).
- Later switch to custom manager group.

Upgrade + logs:

- Run baseline command.
- Confirm action opens and CRUD works for allowed user.

## 4) Step 4 - Sales Order Header Button Only

Scope:

- Inherit sale.order form and add button:
  - action_recalculate_labor_costs

Implementation:

- Add button in header near quotation actions.
- No line columns yet.

Upgrade + logs:

- Run baseline command.
- Confirm button is visible and action executes without errors.

## 5) Step 5 - Add 3 Safe Readonly SOL Columns

Scope:

- Inherit order_line tree and add only computed readonly columns first:
  - x_total_salary
  - x_gosi_amount
  - x_total_service_cost

Implementation:

- Add with optional="show" and readonly="1".
- Keep xpath near existing numeric columns.

Upgrade + logs:

- Run baseline command.
- Confirm Sales Order opens and lines render.

## 6) Step 6 - Add Input Salary Columns

Scope:

- Add editable input columns:
  - x_basic_salary
  - x_housing_allowance
  - x_transport_allowance
  - x_food_allowance

Implementation:

- Use optional="hide" for non-noisy default list.
- Keep labels with FIN prefix for column chooser ordering.

Upgrade + logs:

- Run baseline command.
- Validate onchange/compute still stable when editing lines.

## 7) Step 7 - Add HR Columns

Scope:

- Add HR columns:
  - x_job_name
  - x_nationality
  - x_contract_type
  - x_working_hours

Implementation:

- Use optional="hide" and HR prefixes.
- Keep this step independent from ops fees.

Upgrade + logs:

- Run baseline command.
- Confirm no parse or rendering issues.

## 8) Step 8 - Add Manager-Controlled Fixed Fee Columns

Scope:

- Add readonly fixed fee display columns:
  - x_labor_rules_config_id
  - x_iqama_fee
  - x_work_permit_fee
  - x_visa_or_transfer_fee
  - x_medical_insurance_fee
  - x_government_fees_total

Implementation:

- Keep fee amounts readonly in line tree.
- Temporarily restrict x_labor_rules_config_id visibility/edit to system/manager group.

Upgrade + logs:

- Run baseline command.
- Validate line loads defaults and displays values correctly.

## 9) Step 9 - Add Optional Aggregates on SO Header

Scope:

- Add order-level readonly totals:
  - x_total_service_cost_all_lines
  - x_total_gosi_all_lines

Implementation:

- Place in a compact summary section.

Upgrade + logs:

- Run baseline command.
- Confirm totals display and update correctly.

## 10) Step 10 - Replace Temporary Security with Final Groups

Scope:

- Introduce final custom groups and apply to views:
  - group_recruitment_hr
  - group_recruitment_finance
  - group_recruitment_ops
  - group_recruitment_manager

Implementation:

- Update menu/action/field groups.
- Keep fixed fee edit paths manager-only.

Upgrade + logs:

- Run baseline command.
- Confirm visibility rules by testing 2 users (manager and non-manager).

## 11) Step 11 - Optional Polish (Only After Stability)

Scope:

- Improve labels/order in dots column picker with HR/FIN/OPS prefixes.
- Minor UX cleanups only, no logic change.

Upgrade + logs:

- Run baseline command.
- Confirm no regressions.

## 12) Recommended Commit Rhythm

- One commit per step (or every two very small steps).
- Commit message format:
  - [views][step-X] short description

## 13) Quick Log Checklist Per Step

Check for these strings in logs:

- "Loading module sale_labor_contract_tabbed"
- "Module sale_labor_contract_tabbed loaded"
- "Registry loaded"

Must not appear:

- "ParseError"
- "ValueError: Invalid field"
- "odoo.tools.convert.ParseError"
- "Traceback (most recent call last)"

---

Status: Lazy views implementation plan created with upgrade-and-logs gate after each step.
