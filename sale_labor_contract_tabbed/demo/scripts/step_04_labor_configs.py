"""
Step 04 — Create Labor Rules Configs
======================================
Creates 3 fee configuration records for the labor.rules.config model:

  Basic Labor Package    (is_default=True,  sequence=10)
  Standard Labor Package (is_default=False, sequence=20)
  Premium Labor Package  (is_default=False, sequence=30)

Idempotent: skips creation if name already exists for the current company.

Run with:
  d:\odoo\odoo19\.venv\Scripts\python.exe `
    d:\odoo\odoo19\odoo19\odoo-bin shell `
    -c d:\odoo\odoo19\odoo_conf\odoo19.conf `
    -d odoo19_dev --no-http `
    < d:\odoo\odoo19\projects\bayet_elholol\sale_labor_contract_tabbed\demo\scripts\step_04_labor_configs.py
"""

LaborConfig = env["labor.rules.config"]
company_id = env.company.id

CONFIGS = [
    {
        "name": "Basic Labor Package",
        "is_default": True,
        "sequence": 10,
        "iqama_fee": 650.0,
        "work_permit_fee": 800.0,
        "visa_fee": 500.0,
        "exit_reentry_visa_fee": 300.0,
        "medical_insurance_fee": 400.0,
    },
    {
        "name": "Standard Labor Package",
        "is_default": False,
        "sequence": 20,
        "iqama_fee": 800.0,
        "work_permit_fee": 1000.0,
        "visa_fee": 700.0,
        "exit_reentry_visa_fee": 400.0,
        "medical_insurance_fee": 600.0,
    },
    {
        "name": "Premium Labor Package",
        "is_default": False,
        "sequence": 30,
        "iqama_fee": 1200.0,
        "work_permit_fee": 1500.0,
        "visa_fee": 1000.0,
        "exit_reentry_visa_fee": 600.0,
        "medical_insurance_fee": 900.0,
    },
]

# ── Create / skip ────────────────────────────────────────────────────────────

created = []
skipped = []

for spec in CONFIGS:
    existing = LaborConfig.search(
        [("name", "=", spec["name"]), ("company_id", "=", company_id)], limit=1
    )
    if existing:
        skipped.append(spec["name"])
        continue

    LaborConfig.create({**spec, "company_id": company_id})
    created.append(spec["name"])

# ── Commit ───────────────────────────────────────────────────────────────────

env.cr.commit()

# ── Report ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 55)
print("Step 04 — Labor Rules Configs")
print("=" * 55)
print(f"  Company: {env.company.name} (id={company_id})")
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
print("  Sales > Configuration > Labour Rules Configuration")
print("  Should see 3 records — Basic marked as Default")
print("=" * 55 + "\n")
