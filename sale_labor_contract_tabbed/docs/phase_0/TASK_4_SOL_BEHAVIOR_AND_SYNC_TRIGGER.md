# Task 4: Sales Order Line Behavior and Sync Trigger

Date: 2026-03-18
Module: `sale_labor_contract_tabbed`
Scope: Define when SOL labor logic is activated and how recalculation/sync should run.

## 1) Product Trigger for Labor Logic

## Goal

Apply labor outsourcing calculations only on specific Sales Order lines, not all products.

## Recommended Trigger Design

Use a dedicated service product flag instead of name-only matching.

- Product type: `service`
- Example product name: `Labor Outsourcing`
- Technical trigger field on `product.template` (or `product.product`):
  - `x_is_labor_outsourcing` (Boolean)

Why this approach:

- Name-based checks are fragile (translations, renames, typos).
- Boolean flag is explicit, stable, and easy for business users to control.
- Supports multiple labor products without extra code changes.

## SOL Activation Rule

For each `sale.order.line`:

- If `product_id.product_tmpl_id.x_is_labor_outsourcing == True`:
  - Show/enable labor fields and run labor computations.
- Else:
  - Keep labor fields hidden or readonly, and skip labor computations.

Example Python condition:

```python
def _is_labor_line(line):
    return bool(line.product_id and line.product_id.product_tmpl_id.x_is_labor_outsourcing)
```

## 2) Sync Trigger Design (Real-time vs Recalculate Button)

## Option A: Real-time Sync (On field change)

Implement via `@api.onchange` and compute dependencies.

Pros:

- Immediate feedback for users.
- Lower risk of stale values during editing.

Cons:

- Heavier form interactions if many lines/fields.
- More onchange complexity and potential edge cases during mass edits/imports.

Best for:

- Small-to-medium orders and interactive quoting.

## Option B: Manual Sync (Recalculate button)

Implement explicit action button on order:

- Button label: `Recalculate Labor Costs`
- Applies recalculation to all labor-enabled lines in the order.

Pros:

- Better performance control on large orders.
- Deterministic recalculation step before confirmation.

Cons:

- Users may forget to click button.
- Potential stale values if no safeguards exist.

Best for:

- Large orders, imported data, or complex formulas.

## Recommended Hybrid Strategy

Use both mechanisms together:

- Real-time for core line math while editing (`onchange` + computed fields).
- Manual `Recalculate Labor Costs` button as a final sync/repair action.

Safety guard:

- On `action_confirm`, force one server-side recompute for labor lines before order confirmation.

This gives fast UX and strong data integrity.

## 3) Proposed Technical Behavior Flow

1. User selects product on SOL.
2. System checks `x_is_labor_outsourcing`.
3. If true, labor fields become relevant and defaults load (managerial fixed fees from config).
4. Line computes run (`x_total_salary`, `x_gosi_amount`, `x_government_fees_total`, `x_total_service_cost`).
5. User may click `Recalculate Labor Costs` to force refresh for all labor lines.
6. On order confirmation, server performs final recompute validation.

## 4) Permissions and Sync Ownership

- Non-manager users:
  - Can trigger recalculation button (optional by policy),
  - Cannot edit fixed government/insurance defaults.
- Manager users:
  - Maintain config defaults,
  - Can use override fields if enabled.

## 5) Final Decision Draft

- Triggering product: any service product with `x_is_labor_outsourcing = True`.
- Sync model: Hybrid
  - Real-time recalculation during edit,
  - Plus manual button,
  - Plus mandatory recompute on confirm.

---

Status: SOL behavior and sync trigger design completed for implementation.
