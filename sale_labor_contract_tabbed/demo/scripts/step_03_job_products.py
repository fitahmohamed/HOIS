"""
Step 03 — Create Job Products
===============================
Creates 8 labor job products, each with x_is_labor_outsourcing = True.
Products are assigned to the correct "Labor - *" sub-category from Step 02.

  Site Engineer          → Labor - Engineering
  Senior Engineer        → Labor - Engineering
  Electrician            → Labor - Technical
  Plumber                → Labor - Technical
  Instrumentation Tech   → Labor - Technical
  Control Room Operator  → Labor - Operations
  Safety Officer         → Labor - HSE
  Project Manager        → Labor - Management

Idempotent: skips creation if product name already exists.

Depends on: Step 02 (categories must exist)

Run with:
  d:\odoo\odoo19\.venv\Scripts\python.exe `
    d:\odoo\odoo19\odoo19\odoo-bin shell `
    -c d:\odoo\odoo19\odoo_conf\odoo19.conf `
    -d odoo19_dev --no-http `
    < d:\odoo\odoo19\projects\bayet_elholol\sale_labor_contract_tabbed\demo\scripts\step_03_job_products.py
"""

Category = env["product.category"]
ProductTemplate = env["product.template"]

# ── Resolve categories from Step 02 ─────────────────────────────────────────

def get_cat(name):
    cat = Category.search([("name", "=", name)], limit=1)
    if not cat:
        raise RuntimeError(
            f"Category '{name}' not found. Did you run step_02_product_categories.py first?"
        )
    return cat

cat_engineering = get_cat("Labor - Engineering")
cat_technical   = get_cat("Labor - Technical")
cat_operations  = get_cat("Labor - Operations")
cat_hse         = get_cat("Labor - HSE")
cat_management  = get_cat("Labor - Management")

# ── Product definitions ──────────────────────────────────────────────────────

PRODUCTS = [
    {"name": "Site Engineer",             "categ_id": cat_engineering.id},
    {"name": "Senior Engineer",           "categ_id": cat_engineering.id},
    {"name": "Electrician",               "categ_id": cat_technical.id},
    {"name": "Plumber",                   "categ_id": cat_technical.id},
    {"name": "Instrumentation Technician","categ_id": cat_technical.id},
    {"name": "Control Room Operator",     "categ_id": cat_operations.id},
    {"name": "Safety Officer",            "categ_id": cat_hse.id},
    {"name": "Project Manager",           "categ_id": cat_management.id},
]

# ── Create / skip ────────────────────────────────────────────────────────────

created = []
skipped = []

for spec in PRODUCTS:
    existing = ProductTemplate.search([("name", "=", spec["name"])], limit=1)
    if existing:
        skipped.append(spec["name"])
        continue

    ProductTemplate.create({
        "name": spec["name"],
        "type": "service",
        "list_price": 0.0,
        "categ_id": spec["categ_id"],
        "x_is_labor_outsourcing": True,
        "sale_ok": True,
        "purchase_ok": False,
    })
    created.append(spec["name"])

# ── Commit ───────────────────────────────────────────────────────────────────

env.cr.commit()

# ── Report ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 55)
print("Step 03 — Job Products")
print("=" * 55)
if created:
    print(f"  CREATED  ({len(created)}):")
    for name in created:
        print(f"    + {name}")
if skipped:
    print(f"  SKIPPED  ({len(skipped)}) — already exist:")
    for name in skipped:
        print(f"    ~ {name}")
print("=" * 55)
print("Done. Verify:")
print("  Sales > Products — filter by 'Labor' or browse by category")
print("  Each product should have x_is_labor_outsourcing checked")
print("=" * 55 + "\n")
