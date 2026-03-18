# Task 5: Basic Module Structure Plan (Phase 0 Consolidation)

Date: 2026-03-18
Module: sale_labor_contract_tabbed
Scope: Build a minimal but production-ready module structure based on Task 1 to Task 4 decisions.

## 1) Phase 0 Decisions Consolidated

- Main logic is line-level on sale.order.line.
- Labor logic runs only for products flagged as labor outsourcing.
- Government and fixed insurance fees are manager-maintained defaults.
- Non-manager users can view fixed fees but cannot edit them.
- Sync strategy is hybrid: real-time compute + manual recalculate button + final recompute on confirm.

## 2) Proposed Basic Module Tree

```text
sale_labor_contract_tabbed/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── product_template.py
│   ├── labor_rules_config.py
│   ├── sale_order.py
│   └── sale_order_line.py
├── views/
│   ├── product_template_views.xml
│   ├── labor_rules_config_views.xml
│   ├── sale_order_views.xml
│   └── sale_order_line_views.xml
├── security/
│   ├── security.xml
│   └── ir.model.access.csv
├── data/
│   └── labor_rules_defaults.xml
├── wizard/
│   ├── __init__.py
│   └── labor_recalculate_wizard.py
├── tests/
│   ├── __init__.py
│   ├── test_labor_rules.py
│   ├── test_permissions.py
│   └── test_recalculate_flow.py
└── docs/
    └── phase_0/
        ├── TASK_1_DATA_MODEL_MAPPING.md
        ├── TASK_2_HIDDEN_LOGIC_EXTRACTION.md
        ├── TASK_3_CLEAN_VIEW_LAYOUT_AND_ACCESS.md
        ├── TASK_4_SOL_BEHAVIOR_AND_SYNC_TRIGGER.md
        └── TASK_5_BASIC_MODULE_STRUCTURE_PLAN.md
```

## 3) File-by-File Responsibilities

### __manifest__.py

- Depends on: sale, product, mail (optional, if chatter needed).
- Load order:
  1. security/security.xml
  2. security/ir.model.access.csv
  3. data/labor_rules_defaults.xml
  4. views/product_template_views.xml
  5. views/labor_rules_config_views.xml
  6. views/sale_order_line_views.xml
  7. views/sale_order_views.xml

### models/product_template.py

- Add trigger flag:
  - x_is_labor_outsourcing (Boolean)
- Optional helper constraints for service-type products.

### models/labor_rules_config.py

- New model: labor.rules.config
- Manager-maintained default fees:
  - iqama_fee
  - work_permit_fee
  - visa_fee
  - medical_insurance_fee (if fixed by policy)
  - optional exit_reentry_visa_fee
- Multi-company support:
  - company_id
  - currency_id
  - active

### models/sale_order_line.py

- Core line fields (HR/Finance/Ops buckets).
- Computed fields for totals and cost outputs.
- Related/computed readonly fields for fixed fees from labor.rules.config.
- Product trigger method:
  - _is_labor_line() based on x_is_labor_outsourcing.
- Onchange/default logic to load managerial defaults when labor product selected.

### models/sale_order.py

- Optional aggregate fields from lines:
  - x_total_service_cost_all_lines
  - x_total_gosi_all_lines
- Recalculate action method:
  - action_recalculate_labor_costs()
- Safety recompute before confirm.

### views/sale_order_line_views.xml

- Inject line columns into order_line tree.
- Use optional="show/hide" for dots menu behavior.
- Use field labels with prefixes HR -, FIN -, OPS - for practical grouping.
- Keep fixed fee fields readonly for all visible roles.

### views/sale_order_views.xml

- Add header button: Recalculate Labor Costs.
- Optional readonly summary block for aggregate totals.

### views/labor_rules_config_views.xml

- Config tree/form for manager maintenance.
- Restrict menu/action to manager group.

### security/security.xml

- Define groups:
  - group_recruitment_hr
  - group_recruitment_finance
  - group_recruitment_ops
  - group_recruitment_manager

### security/ir.model.access.csv

- labor.rules.config:
  - manager: read/write/create/unlink
  - other groups: read only (or no access if policy requires)
- Ensure no non-manager write path to fixed defaults.

## 4) Implementation Order (Execution Plan)

1. Create manifest, init files, and empty model/view/security scaffolding.
2. Implement labor.rules.config model and ACL first.
3. Add product trigger flag (x_is_labor_outsourcing).
4. Add sale.order.line fields and compute methods.
5. Add sale.order aggregates and recalculate action.
6. Add line tree columns with optional flags and groups.
7. Add manager-only config screens and menu entries.
8. Add confirm-time recompute guard.
9. Add tests for formulas, trigger behavior, and permissions.

## 5) Minimum Viable Field Set (Phase 0)

- Trigger and references:
  - product.template.x_is_labor_outsourcing
  - sale.order.line.x_labor_rules_config_id
- Salary input fields:
  - x_basic_salary
  - x_housing_allowance
  - x_transport_allowance
  - x_food_allowance
- Core computed fields:
  - x_total_salary
  - x_gosi_amount
  - x_government_fees_total
  - x_total_service_cost
- Fixed fee readonly fields on line:
  - x_iqama_fee
  - x_work_permit_fee
  - x_visa_or_transfer_fee
  - x_medical_insurance_fee

## 6) Sync Strategy to Implement in Code

- Real-time:
  - Use compute dependencies and targeted onchange for interactive updates.
- Manual:
  - Add Recalculate Labor Costs button on sale.order.
- Safety:
  - Force server-side recompute in action_confirm before final confirmation.

## 7) Risk Controls and Validation

- Validate nationality normalization for GOSI rate selection.
- Avoid name-based product trigger logic.
- Prevent direct write on fixed fee fields for non-managers.
- Cover imported orders with button and confirm-time recompute.

## 8) Acceptance Criteria for Phase 0

- Labor calculations apply only to labor-flagged products.
- Line columns are available in Sales Order line dots menu.
- Fixed government/insurance values are manager-controlled defaults.
- Non-managers can view fixed fee outputs but cannot edit them.
- Recalculate button and confirm-time recompute both work.
- Core formula tests and permission tests pass.

---

Status: Basic module structure plan is defined and aligned with all phase_0 documents.
