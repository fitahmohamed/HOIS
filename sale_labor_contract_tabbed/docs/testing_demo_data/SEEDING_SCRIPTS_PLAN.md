# Demo Data Seeding Scripts Plan — Option B (Python / Odoo Shell)

Date: 2026-03-18
Module: sale_labor_contract_tabbed
Approach: Multiple standalone Python scripts, each run via `odoo shell`.
          Apply one script at a time, verify after each, then continue.

---

## Why Python Scripts Instead of XML

| Concern | XML Demo | Python Scripts |
|---------|----------|----------------|
| Control flow (skip if exists) | ❌ always re-creates | ✅ can guard with `search` |
| Assert computed values inline | ❌ | ✅ |
| Run on existing DB without reinstall | ❌ | ✅ |
| Step-by-step with pause/verify | ❌ | ✅ |
| Readable values & comments | ✅ | ✅ |

---

## How to Run Each Script

```powershell
# General pattern — replace step_XX_name.py with the script to run
d:\odoo\odoo19\.venv\Scripts\python.exe `
  d:\odoo\odoo19\odoo19\odoo-bin shell `
  -c d:\odoo\odoo19\odoo_conf\odoo19.conf `
  -d odoo19_dev `
  --no-http `
  < d:\odoo\odoo19\projects\bayet_elholol\sale_labor_contract_tabbed\demo\scripts\step_XX_name.py
```

Each script:
- Is **idempotent** — searches first, skips creation if record already exists
- Calls `env.cr.commit()` at the end to persist changes
- Prints a summary of what was created / already existed
- Raises a clear error if a required dependency is missing

---

## Script Inventory

| Step | File | Creates | Depends On |
|------|------|---------|------------|
| 01 | `step_01_users.py` | 2 demo users | `base.group_user`, `sales_team.group_sale_manager` |
| 02 | `step_02_product_categories.py` | 1 parent + 5 child categories | nothing |
| 03 | `step_03_job_products.py` | 8 labor job products | Step 02 categories |
| 04 | `step_04_labor_configs.py` | 3 fee config records | `res.company` (env default) |
| 05 | `step_05_partners.py` | 2 demo customers | Saudi Arabia country |
| 06 | `step_06_sale_orders.py` | 3 orders + 8 lines | Steps 03, 04, 05 |

---

## Step 01 — Demo Users

**File:** `demo/scripts/step_01_users.py`

**Creates:**

| Login | Name | Groups |
|-------|------|--------|
| `demo.hr@demo.local` | Demo HR User | `base.group_user` only |
| `demo.manager@demo.local` | Demo Sales Manager | `sales_team.group_sale_manager` |

**Key implementation notes:**
- Search by `login` before creating — skip if exists
- Password set via `user.password = 'demo1234'` after creation
- Manager user: add group via `(4, ref_id)` command on `groups_id`
- Both users need a linked `res.partner` record (Odoo creates it automatically via `res.users`)

**Verify after running:**
```
Settings > Users — 2 new users listed
Log in as demo.hr@demo.local with password demo1234 — should succeed
Log in as demo.manager@demo.local with password demo1234 — should succeed
```

---

## Step 02 — Product Categories

**File:** `demo/scripts/step_02_product_categories.py`

**Creates:**

| Internal Reference | Parent |
|--------------------|--------|
| Labor | (none — top level) |
| Labor - Engineering | Labor |
| Labor - Technical | Labor |
| Labor - Operations | Labor |
| Labor - HSE | Labor |
| Labor - Management | Labor |

**Key implementation notes:**
- Model: `product.category`
- Search by `name` + `parent_id` before creating
- Create parent first, then children in a loop

**Verify after running:**
```
Inventory > Configuration > Product Categories
OR
Products > search a product > Category field dropdown
Should see Labor and its 5 sub-categories
```

---

## Step 03 — Job Products

**File:** `demo/scripts/step_03_job_products.py`

**Creates 8 products:**

| Name | Category | x_is_labor_outsourcing |
|------|----------|------------------------|
| Site Engineer | Labor - Engineering | True |
| Senior Engineer | Labor - Engineering | True |
| Electrician | Labor - Technical | True |
| Plumber | Labor - Technical | True |
| Instrumentation Technician | Labor - Technical | True |
| Control Room Operator | Labor - Operations | True |
| Safety Officer | Labor - HSE | True |
| Project Manager | Labor - Management | True |

**Key implementation notes:**
- Model: `product.template`
- `type = 'service'`
- `list_price = 0`
- `x_is_labor_outsourcing = True`
- Search by `name` before creating — skip if found
- Resolve category by name from Step 02

**Verify after running:**
```
Sales > Products — filter by "Labor" — 8 products shown
Open any one — x_is_labor_outsourcing checkbox is checked
```

---

## Step 04 — Labor Rules Configs

**File:** `demo/scripts/step_04_labor_configs.py`

**Creates 3 records:**

| Name | is_default | iqama | work_permit | visa | exit_reentry | medical |
|------|-----------|-------|-------------|------|--------------|---------|
| Basic Labor Package | True | 650 | 800 | 500 | 300 | 400 |
| Standard Labor Package | False | 800 | 1000 | 700 | 400 | 600 |
| Premium Labor Package | False | 1200 | 1500 | 1000 | 600 | 900 |

**Key implementation notes:**
- Model: `labor.rules.config`
- Search by `name` + `company_id` before creating
- Create Basic first (since `is_default=True`) — the `_check_single_default_per_company`
  constraint will block a second default, so Standard and Premium must have `is_default=False`
- `company_id = env.company.id`

**Verify after running:**
```
Sales > Configuration > Labour Rules Configuration
3 records listed — Basic marked as Default
```

---

## Step 05 — Demo Partners (Customers)

**File:** `demo/scripts/step_05_partners.py`

**Creates:**

| Name | `is_company` | Country | Customer Rank |
|------|-------------|---------|---------------|
| Al Futtaim Facilities | True | Saudi Arabia | 1 |
| Saudi Aramco Facilities | True | Saudi Arabia | 1 |

**Key implementation notes:**
- Model: `res.partner`
- Search by `name` before creating
- Resolve Saudi Arabia via `env['res.country'].search([('code', '=', 'SA')])`
- `customer_rank = 1` makes them appear in customer dropdowns

**Verify after running:**
```
Sales > Customers — both partners visible
```

---

## Step 06 — Sale Orders and Lines

**File:** `demo/scripts/step_06_sale_orders.py`

**Creates 3 orders + 8 lines total:**

### Order 1 — Mixed Nationalities (Basic Package)
Customer: Al Futtaim Facilities

| Product | x_job_name | x_nationality | x_contract_type | x_working_hours | x_basic_salary | x_housing | x_transport | x_food | x_other | x_contract_days | x_annual_leave_days | x_air_ticket | x_medical_exam | x_municipality | x_linkage | x_service_fee |
|---------|-----------|---------------|----------------|----------------|---------------|-----------|-------------|--------|---------|----------------|---------------------|-------------|---------------|----------------|----------|--------------|
| Site Engineer | Site Engineer | Saudi | single | 48 | 5000 | 2000 | 500 | 400 | 0 | 365 | 21 | 300 | 200 | 100 | 150 | 500 |
| Electrician | Electrician | Egyptian | single | 48 | 2500 | 800 | 300 | 0 | 0 | 365 | 21 | 250 | 150 | 100 | 100 | 300 |
| Plumber | Plumber | Indian | family | 48 | 2200 | 700 | 300 | 0 | 0 | 365 | 30 | 300 | 150 | 100 | 100 | 300 |

### Order 2 — Technical Staff (Standard Package)
Customer: Saudi Aramco Facilities

| Product | x_job_name | x_nationality | x_contract_type | x_working_hours | x_basic_salary | x_housing | x_transport | x_food | x_other | x_contract_days | x_annual_leave_days | x_air_ticket | x_medical_exam | x_municipality | x_linkage | x_service_fee |
|---------|-----------|---------------|----------------|----------------|---------------|-----------|-------------|--------|---------|----------------|---------------------|-------------|---------------|----------------|----------|--------------|
| Instrumentation Technician | Instrumentation Tech | Pakistani | single | 48 | 3000 | 1000 | 400 | 0 | 0 | 365 | 21 | 280 | 200 | 100 | 120 | 350 |
| Control Room Operator | Control Room Operator | Saudi | family | 48 | 6000 | 2500 | 600 | 500 | 200 | 365 | 30 | 0 | 200 | 100 | 150 | 600 |
| Safety Officer | Safety Officer | Egyptian | single | 40 | 3500 | 1200 | 400 | 0 | 0 | 365 | 21 | 280 | 200 | 100 | 120 | 400 |

### Order 3 — Supervisory (Premium Package)
Customer: Al Futtaim Facilities

| Product | x_job_name | x_nationality | x_contract_type | x_working_hours | x_basic_salary | x_housing | x_transport | x_food | x_other | x_contract_days | x_annual_leave_days | x_air_ticket | x_medical_exam | x_municipality | x_linkage | x_service_fee |
|---------|-----------|---------------|----------------|----------------|---------------|-----------|-------------|--------|---------|----------------|---------------------|-------------|---------------|----------------|----------|--------------|
| Project Manager | Project Manager | Saudi | family | 40 | 12000 | 4000 | 1000 | 800 | 500 | 365 | 30 | 0 | 300 | 150 | 200 | 1500 |
| Senior Engineer | Senior Engineer | British | single | 40 | 10000 | 3000 | 800 | 0 | 0 | 365 | 25 | 800 | 300 | 150 | 200 | 1200 |

**Key implementation notes:**
- Model: `sale.order` + `sale.order.line`
- Search by `partner_id` + `name` (order name) before creating — skip if exists
- Lines created via `sale.order.line` directly (not nested `order_line` write)
- Resolve product via `product.product` (variant), not `product.template`
- Set `x_labor_rules_config_id` explicitly per line — do not rely on default auto-select
- All monetary fields are in company currency (SAR assumed)
- After creating lines, call `order._compute_amounts()` to trigger totals

**Verify after running:**
```
Sales > Orders — 3 orders with names like S00001, S00002, S00003
Click any order — order lines tab shows correct number of lines
Click ↗ on a line — popup with Financial / HR Details / Operations tabs
Operations tab — fees match the config assigned to that line
GOSI: Saudi lines show 11.75%, others show 2%
```

---

## Expected Computed Values for Spot-Check

### Order 1 — Line 1 (Site Engineer, Saudi, Basic Package)

| Computed Field | Expected Value |
|---------------|---------------|
| `x_total_salary` | 5000 + 2000 + 500 + 400 = **7,900 SAR** |
| `x_gosi_rate` | **11.75%** |
| `x_gosi_amount` | (5000 + 2000) × 0.1175 = **822.50 SAR** |
| `x_iqama_fee` | **650 SAR** (from Basic config) |
| `x_work_permit_fee` | **800 SAR** |
| `x_visa_or_transfer_fee` | **500 SAR** |
| `x_exit_reentry_visa_fee` | **300 SAR** |
| `x_government_fees_total` | 650+800+500+300 = **2,250 SAR** |
| `x_vacation_eos_accrual` | (7900/30) × (365/12) = **7,996.53 SAR** |
| `x_medical_insurance_fee` | **400 SAR** (from Basic config) |

### Order 1 — Line 2 (Electrician, Egyptian, Basic Package)

| Computed Field | Expected Value |
|---------------|---------------|
| `x_total_salary` | 2500 + 800 + 300 = **3,600 SAR** |
| `x_gosi_rate` | **2%** |
| `x_gosi_amount` | (2500 + 800) × 0.02 = **66 SAR** |
| `x_government_fees_total` | **2,250 SAR** (same config) |

---

## Cleanup Script (Optional)

**File:** `demo/scripts/step_00_cleanup.py`

Removes all records created by the seeding scripts in reverse dependency order:
1. Delete `sale.order.line` where `order_id` is a demo order
2. Delete `sale.order` where `name` starts with demo prefix
3. Delete `labor.rules.config` where name matches demo names
4. Delete `product.template` where `x_is_labor_outsourcing = True` and name in demo list
5. Delete `product.category` where name starts with "Labor"
6. Delete `res.users` where login in `['demo.hr@demo.local', 'demo.manager@demo.local']`
7. Delete `res.partner` where name in demo partner names

> Run this to reset the DB to pre-seed state before re-running all scripts from Step 01.

---

## Run Order Summary

```
Step 00  [optional]  step_00_cleanup.py          — wipe previous seed data
Step 01              step_01_users.py             — 2 demo users
Step 02              step_02_product_categories.py — 6 categories
Step 03              step_03_job_products.py       — 8 job products
Step 04              step_04_labor_configs.py      — 3 fee configs
Step 05              step_05_partners.py           — 2 customers
Step 06              step_06_sale_orders.py        — 3 orders + 8 lines
```

After all steps → run through Verification Checklist in `DEMO_DATA_PLAN.md § 10`.
