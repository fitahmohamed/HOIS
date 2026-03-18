"""
Step 05 — Create Demo Customers
=================================
Creates 2 demo customer partners:

  Al Futtaim Facilities      (Saudi Arabia)
  Saudi Aramco Facilities    (Saudi Arabia)

Idempotent: skips creation if partner name already exists.

Run with:
  d:\odoo\odoo19\.venv\Scripts\python.exe `
    d:\odoo\odoo19\odoo19\odoo-bin shell `
    -c d:\odoo\odoo19\odoo_conf\odoo19.conf `
    -d odoo19_dev --no-http `
    < d:\odoo\odoo19\projects\bayet_elholol\sale_labor_contract_tabbed\demo\scripts\step_05_partners.py
"""

Partner = env["res.partner"]
Country = env["res.country"]

# ── Resolve Saudi Arabia ─────────────────────────────────────────────────────

sa = Country.search([("code", "=", "SA")], limit=1)
if not sa:
    raise RuntimeError("Country 'SA' (Saudi Arabia) not found in database.")

# ── Partner definitions ──────────────────────────────────────────────────────

PARTNERS = [
    {"name": "Al Futtaim Facilities"},
    {"name": "Saudi Aramco Facilities"},
]

# ── Create / skip ────────────────────────────────────────────────────────────

created = []
skipped = []

for spec in PARTNERS:
    existing = Partner.search([("name", "=", spec["name"]), ("is_company", "=", True)], limit=1)
    if existing:
        skipped.append(spec["name"])
        continue

    Partner.create({
        "name": spec["name"],
        "is_company": True,
        "country_id": sa.id,
        "customer_rank": 1,
    })
    created.append(spec["name"])

# ── Commit ───────────────────────────────────────────────────────────────────

env.cr.commit()

# ── Report ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 55)
print("Step 05 — Demo Customers")
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
print("  Sales > Customers — look for Al Futtaim and Saudi Aramco")
print("=" * 55 + "\n")
