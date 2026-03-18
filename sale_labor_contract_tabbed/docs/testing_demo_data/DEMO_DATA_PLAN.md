# Demo Data Plan — sale_labor_contract_tabbed

Date: 2026-03-18
Module: sale_labor_contract_tabbed
Goal: Create realistic demo data that exercises every field of the module so
      functional testing and UI review can be done on a fresh database without
      manually entering records.

---

## 1. Scope — What We Need to Seed

| # | Object | Why Needed |
|---|--------|------------|
| 1 | `res.users` (demo users) | Test visibility rules per group without using admin |
| 2 | `res.partner` (customers) | Required for sale orders |
| 3 | `labor.rules.config` (fee tables) | Auto-selected on labor lines; drives all fee fields |
| 4 | `product.template` (job products) | One product per job role; `x_is_labor_outsourcing = True` triggers labor tab |
| 5 | `sale.order` + `sale.order.line` | The main object; one order per scenario |

---

## 2. Demo Users

Two users covering both access levels used in the module.

### User A — Internal User (HR / OPS viewer)

| Field | Value |
|-------|-------|
| `name` | Demo HR User |
| `login` | `demo.hr@demo.local` |
| `password` | `demo1234` |
| `groups` | `base.group_user` (Internal User only) |
| Can see | HR Details tab, OPS tab (fees readonly), totals columns |
| Cannot see | Financial tab (salary breakdown), Rules Config column, Labour Rules menu |

### User B — Sales Manager

| Field | Value |
|-------|-------|
| `name` | Demo Sales Manager |
| `login` | `demo.manager@demo.local` |
| `password` | `demo1234` |
| `groups` | `sales_team.group_sale_manager` (implies `base.group_user`) |
| Can see | All tabs including Financial, salary columns, Rules Config, Labour Rules menu |

> **Testing workflow:**
> Log in as `demo.hr@demo.local` — confirm Financial tab is hidden.
> Log in as `demo.manager@demo.local` — confirm all tabs and menus are visible.

---

## 3. Labor Rules Config Records

Three configs covering different fee tiers: basic, standard, and premium.

### Config A — Basic Package

| Field | Value |
|-------|-------|
| `name` | Basic Labor Package |
| `is_default` | True (auto-selected for company) |
| `sequence` | 10 |
| `iqama_fee` | 650 SAR |
| `work_permit_fee` | 800 SAR |
| `visa_fee` | 500 SAR |
| `exit_reentry_visa_fee` | 300 SAR |
| `medical_insurance_fee` | 400 SAR |

### Config B — Standard Package

| Field | Value |
|-------|-------|
| `name` | Standard Labor Package |
| `is_default` | False |
| `sequence` | 20 |
| `iqama_fee` | 800 SAR |
| `work_permit_fee` | 1000 SAR |
| `visa_fee` | 700 SAR |
| `exit_reentry_visa_fee` | 400 SAR |
| `medical_insurance_fee` | 600 SAR |

### Config C — Premium Package

| Field | Value |
|-------|-------|
| `name` | Premium Labor Package |
| `is_default` | False |
| `sequence` | 30 |
| `iqama_fee` | 1200 SAR |
| `work_permit_fee` | 1500 SAR |
| `visa_fee` | 1000 SAR |
| `exit_reentry_visa_fee` | 600 SAR |
| `medical_insurance_fee` | 900 SAR |

---

## 4. Job Products (product.template)

Each product represents a specific job role. All have `x_is_labor_outsourcing = True`.
Sale price is 0 — the real billable cost is driven by `x_total_service_cost`.

| XML ID | Product Name | Category | Use in Orders |
|--------|-------------|----------|---------------|
| `product_job_site_engineer` | Site Engineer | Labor - Engineering | Order 1 |
| `product_job_electrician` | Electrician | Labor - Technical | Order 1 |
| `product_job_plumber` | Plumber | Labor - Technical | Order 1 |
| `product_job_instrumentation_tech` | Instrumentation Technician | Labor - Technical | Order 2 |
| `product_job_control_room_operator` | Control Room Operator | Labor - Operations | Order 2 |
| `product_job_safety_officer` | Safety Officer | Labor - HSE | Order 2 |
| `product_job_project_manager` | Project Manager | Labor - Management | Order 3 |
| `product_job_senior_engineer` | Senior Engineer | Labor - Engineering | Order 3 |

> **Why one product per job?**
> Allows users to pick a job from the product dropdown on the SO line and have the
> `x_job_name` pre-filled via a future onchange improvement. Also makes reporting
> by job type possible using standard product filtering.

> **Product Category** (`Labor - *`) should be created as internal categories
> under a parent `Labor` category — this keeps labor products isolated in the
> product catalog and makes them easy to filter.

---

## 5. Demo Customers (res.partner)

| XML ID | Name | Country |
|--------|------|---------|
| `partner_demo_alfuttaim` | Al Futtaim Facilities | Saudi Arabia |
| `partner_demo_aramco` | Saudi Aramco Facilities | Saudi Arabia |

---

## 6. Sale Orders + Lines

### Order 1 — Mixed Nationalities (tests GOSI rate split)

- **Customer:** Al Futtaim Facilities
- **Config used:** Basic Labor Package

| # | Job Name | Nationality | Contract Type | Working Hrs | Basic | Housing | Transport | Food | Other | Contract Days | Leave Days | Air Ticket | Medical Exam | Municipality | Linkage | Service Fee |
|---|----------|-------------|---------------|-------------|-------|---------|-----------|------|-------|--------------|------------|------------|--------------|--------------|---------|-------------|
| 1 | Site Engineer | Saudi | single | 48 | 5000 | 2000 | 500 | 400 | 0 | 365 | 21 | 300 | 200 | 100 | 150 | 500 |
| 2 | Electrician | Egyptian | single | 48 | 2500 | 800 | 300 | 0 | 0 | 365 | 21 | 250 | 150 | 100 | 100 | 300 |
| 3 | Plumber | Indian | family | 48 | 2200 | 700 | 300 | 0 | 0 | 365 | 30 | 300 | 150 | 100 | 100 | 300 |

Expected GOSI check:
- Line 1 (Saudi): rate = 11.75% → GOSI = (5000 + 2000) × 0.1175 = **822.50 SAR/month**
- Line 2 (Egyptian): rate = 2% → GOSI = (2500 + 800) × 0.02 = **66 SAR/month**
- Line 3 (Indian): rate = 2% → GOSI = (2200 + 700) × 0.02 = **58 SAR/month**

---

### Order 2 — Technical Staff (tests Standard Package fees)

- **Customer:** Saudi Aramco Facilities
- **Config used:** Standard Labor Package

| # | Job Name | Nationality | Contract Type | Working Hrs | Basic | Housing | Transport | Food | Other | Contract Days | Leave Days | Air Ticket | Medical Exam | Municipality | Linkage | Service Fee |
|---|----------|-------------|---------------|-------------|-------|---------|-----------|------|-------|--------------|------------|------------|--------------|--------------|---------|-------------|
| 1 | Instrumentation Tech | Pakistani | single | 48 | 3000 | 1000 | 400 | 0 | 0 | 365 | 21 | 280 | 200 | 100 | 120 | 350 |
| 2 | Control Room Operator | Saudi | family | 48 | 6000 | 2500 | 600 | 500 | 200 | 365 | 30 | 0 | 200 | 100 | 150 | 600 |
| 3 | Safety Officer | Egyptian | single | 40 | 3500 | 1200 | 400 | 0 | 0 | 365 | 21 | 280 | 200 | 100 | 120 | 400 |

---

### Order 3 — Supervisory (tests Premium Package + family contract)

- **Customer:** Al Futtaim Facilities
- **Config used:** Premium Labor Package

| # | Job Name | Nationality | Contract Type | Working Hrs | Basic | Housing | Transport | Food | Other | Contract Days | Leave Days | Air Ticket | Medical Exam | Municipality | Linkage | Service Fee |
|---|----------|-------------|---------------|-------------|-------|---------|-----------|------|-------|--------------|------------|------------|--------------|--------------|---------|-------------|
| 1 | Project Manager | Saudi | family | 40 | 12000 | 4000 | 1000 | 800 | 500 | 365 | 30 | 0 | 300 | 150 | 200 | 1500 |
| 2 | Senior Engineer | British | single | 40 | 10000 | 3000 | 800 | 0 | 0 | 365 | 25 | 800 | 300 | 150 | 200 | 1200 |

---

## 7. Field Coverage Checklist

### `labor.rules.config`

| Field | Covered |
|-------|---------|
| `name` | ✅ 3 configs |
| `is_default` | ✅ Config A = True, others = False |
| `sequence` | ✅ 10 / 20 / 30 |
| `company_id` | ✅ auto from env |
| `iqama_fee` | ✅ |
| `work_permit_fee` | ✅ |
| `visa_fee` | ✅ |
| `exit_reentry_visa_fee` | ✅ |
| `medical_insurance_fee` | ✅ |

### `product.template`

| Field | Covered |
|-------|---------|
| `x_is_labor_outsourcing` | ✅ all 3 products = True |

### `sale.order.line` — all x_ fields

| Field | Covered |
|-------|---------|
| `x_job_name` | ✅ varied per line |
| `x_nationality` | ✅ Saudi / Egyptian / Indian / Pakistani / British |
| `x_contract_type` | ✅ single + family both present |
| `x_working_hours` | ✅ 40h and 48h |
| `x_contract_days` | ✅ 365 (all) |
| `x_annual_leave_days` | ✅ 21 / 25 / 30 |
| `x_basic_salary` | ✅ |
| `x_housing_allowance` | ✅ |
| `x_transport_allowance` | ✅ |
| `x_food_allowance` | ✅ zero and non-zero |
| `x_other_allowances` | ✅ zero and non-zero |
| `x_medical_exam_fee` | ✅ |
| `x_municipality_card_fee` | ✅ |
| `x_linkage_ajeer_fee` | ✅ |
| `x_service_fee` | ✅ |
| `x_air_ticket_accrual_monthly` | ✅ zero (Saudi) and non-zero |
| `x_labor_rules_config_id` | ✅ Basic / Standard / Premium |
| `x_is_labor_line` | ✅ computed from product flag |
| `x_salary_details_total` | ✅ computed |
| `x_total_salary` | ✅ computed |
| `x_gosi_rate` | ✅ computed — 11.75% Saudi / 2% non-Saudi |
| `x_gosi_amount` | ✅ computed |
| `x_iqama_fee` | ✅ related from config |
| `x_work_permit_fee` | ✅ related from config |
| `x_visa_or_transfer_fee` | ✅ related from config |
| `x_exit_reentry_visa_fee` | ✅ related from config |
| `x_medical_insurance_fee` | ✅ related from config |
| `x_government_fees_total` | ✅ computed |
| `x_vacation_eos_accrual` | ✅ computed |
| `x_total_service_cost` | ✅ computed |

---

## 8. Implementation Approach — XML vs Python

Two options. Choose one.

### Option A — XML Demo Data File (Recommended for Odoo modules)

**File:** `demo/demo_data.xml`

Pros:
- Loaded automatically when module is installed with `--load-demo`
- Declarative, easy to read and review
- Odoo-native pattern

Cons:
- Cannot easily compute expected values inline (computed fields fill automatically)
- Order of records matters (partner before order, config before line)

Steps:
1. Create `demo/` folder
2. Create `demo/demo_data.xml` with records in dependency order:
   - `res.partner` records
   - `labor.rules.config` records
   - `product.template` records
   - `sale.order` records
   - `sale.order.line` records (nested inside order or separate)
3. Add `"demo": ["demo/demo_data.xml"]` to `__manifest__.py`
4. Reinstall module with `--load-demo` flag
5. Verify computed fields populated correctly in UI

### Option B — Python Script (One-off seeding)

**File:** `demo/seed_demo.py` (run with `odoo shell`)

Pros:
- Can assert computed values immediately
- Can loop and generate large datasets easily

Cons:
- Not loaded automatically
- Requires shell access to run

---

## 9. Implementation Order (XML approach)

Records must be declared in dependency order inside the XML file:

```
1. res.partner (customers) ×2          no dependencies
2. res.users (demo users) ×2           depends on: base.group_user, sales_team.group_sale_manager
3. product.category (Labor, sub-cats)  no dependencies
4. product.template (job products) ×8  depends on: product.category
5. labor.rules.config ×3               depends on: res.company (auto from env)
6. sale.order ×3                       depends on: res.partner
7. sale.order.line ×8                  depends on: sale.order + product.product + labor.rules.config
```

> `res.users` in XML demo data: create via `<record model="res.users">` with
> `<field name="groups_id" eval="[(4, ref('sales_team.group_sale_manager'))]">`
> for the manager user. Password must be set via `<field name="password">demo1234</field>`.

---

## 10. Verification Checklist After Loading Demo Data

### Users & Groups
- [ ] Log in as `demo.hr@demo.local` → Financial tab NOT visible on line popup
- [ ] Log in as `demo.hr@demo.local` → Labour Rules Config menu NOT visible
- [ ] Log in as `demo.hr@demo.local` → HR Details and Operations tabs ARE visible
- [ ] Log in as `demo.manager@demo.local` → All 3 tabs visible
- [ ] Log in as `demo.manager@demo.local` → Labour Rules Config menu IS visible

### Products
- [ ] Products > search "Labor" → 8 job products listed
- [ ] Each product has `x_is_labor_outsourcing` checked
- [ ] Products are grouped under `Labor - Engineering / Technical / Operations / HSE / Management` categories

### Orders & Lines
- [ ] Sales > Orders — 3 demo orders visible
- [ ] Order 1 has 3 lines (Engineer, Electrician, Plumber)
- [ ] Order 2 has 3 lines (Instrumentation Tech, Control Room Operator, Safety Officer)
- [ ] Order 3 has 2 lines (Project Manager, Senior Engineer)
- [ ] Open any line popup → HR Details tab shows job/nationality/contract
- [ ] Open any line popup → Operations tab shows fees pulled from config
- [ ] Line popup → Financial tab visible to manager only

### Computed Values
- [ ] Saudi nationality lines → GOSI rate = 11.75%
- [ ] Non-Saudi lines → GOSI rate = 2%
- [ ] Config A (Basic) is set as default — auto-selected on new lines
- [ ] Labor Summary panel on SO header shows aggregate totals
- [ ] Labour Rules Config menu → shows 3 records

---

## 11. Next Action

Implement Option A (XML demo data).

File to create: `demo/demo_data.xml`
Manifest update: add `"demo": ["demo/demo_data.xml"]`
Install command:

```powershell
d:\odoo\odoo19\.venv\Scripts\python.exe d:\odoo\odoo19\odoo19\odoo-bin `
  -c d:\odoo\odoo19\odoo_conf\odoo19.conf `
  -u sale_labor_contract_tabbed `
  --stop-after-init
```

> Note: For a fresh DB install with demo: add `--load-demo` to the init command.
> For an existing DB where module is already installed: use `-u` — demo data
> only loads on first install (`-i`), not on upgrade. To force reload demo data
> on an existing DB, delete and recreate the DB then reinstall with `-i` and
> `--load-demo`.
