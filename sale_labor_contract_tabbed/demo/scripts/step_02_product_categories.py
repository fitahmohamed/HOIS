"""
Step 02 — Create Product Categories
=====================================
Creates a parent "Labor" category and 5 sub-categories:

  Labor
  ├── Labor - Engineering
  ├── Labor - Technical
  ├── Labor - Operations
  ├── Labor - HSE
  └── Labor - Management

Idempotent: skips creation if the category already exists (matched by name + parent).

Run with:
  d:\odoo\odoo19\.venv\Scripts\python.exe `
    d:\odoo\odoo19\odoo19\odoo-bin shell `
    -c d:\odoo\odoo19\odoo_conf\odoo19.conf `
    -d odoo19_dev --no-http `
    < d:\odoo\odoo19\projects\bayet_elholol\sale_labor_contract_tabbed\demo\scripts\step_02_product_categories.py
"""

Category = env["product.category"]

created = []
skipped = []

# ── Parent category ──────────────────────────────────────────────────────────

parent = Category.search([("name", "=", "Labor"), ("parent_id", "=", False)], limit=1)
if parent:
    skipped.append("Labor (parent)")
else:
    parent = Category.create({"name": "Labor"})
    created.append("Labor (parent)")

# ── Sub-categories ───────────────────────────────────────────────────────────

SUBCATEGORIES = [
    "Labor - Engineering",
    "Labor - Technical",
    "Labor - Operations",
    "Labor - HSE",
    "Labor - Management",
]

for name in SUBCATEGORIES:
    existing = Category.search(
        [("name", "=", name), ("parent_id", "=", parent.id)], limit=1
    )
    if existing:
        skipped.append(name)
    else:
        Category.create({"name": name, "parent_id": parent.id})
        created.append(name)

# ── Commit ───────────────────────────────────────────────────────────────────

env.cr.commit()

# ── Report ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 55)
print("Step 02 — Product Categories")
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
print("  Inventory > Configuration > Product Categories")
print("  Should see: Labor (parent) + 5 sub-categories")
print("=" * 55 + "\n")
