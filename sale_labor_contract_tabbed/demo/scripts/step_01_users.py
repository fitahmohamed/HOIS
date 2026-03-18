"""
Step 01 — Create Demo Users
============================
Creates two demo users covering the two access levels used by this module:

  demo.hr@demo.local      — Internal User only (base.group_user)
  demo.manager@demo.local — Sales Manager (sales_team.group_sale_manager)

Idempotent: skips creation if the login already exists.

Run with:
  d:\odoo\odoo19\.venv\Scripts\python.exe `
    d:\odoo\odoo19\odoo19\odoo-bin shell `
    -c d:\odoo\odoo19\odoo_conf\odoo19.conf `
    -d odoo19_dev --no-http `
    < d:\odoo\odoo19\projects\bayet_elholol\sale_labor_contract_tabbed\demo\scripts\step_01_users.py
"""

DEMO_PASSWORD = "demo1234"

USERS = [
    {
        "name": "Demo HR User",
        "login": "demo.hr@demo.local",
        "extra_groups": [],  # base.group_user added via default_groups()
    },
    {
        "name": "Demo Sales Manager",
        "login": "demo.manager@demo.local",
        "extra_groups": ["sales_team.group_sale_manager"],
    },
]

# ── Resolve required group refs ──────────────────────────────────────────────

group_user = env.ref("base.group_user")
group_sale_manager = env.ref("sales_team.group_sale_manager")

GROUP_MAP = {
    "sales_team.group_sale_manager": group_sale_manager,
}

# ── Create / skip users ──────────────────────────────────────────────────────

created = []
skipped = []

for spec in USERS:
    existing = env["res.users"].search([("login", "=", spec["login"])], limit=1)
    if existing:
        skipped.append(spec["login"])
        continue

    # In Odoo 19 the field is group_ids (not groups_id).
    # base.group_user is included via _default_groups() automatically.
    # Extra groups are appended with (4, id) after creation to avoid constraint conflicts.
    user = env["res.users"].create(
        {
            "name": spec["name"],
            "login": spec["login"],
            "email": spec["login"],
        }
    )
    for g in spec["extra_groups"]:
        grp = GROUP_MAP.get(g)
        if grp:
            user.write({"group_ids": [(4, grp.id)]})
    user.password = DEMO_PASSWORD
    created.append(spec["login"])

# ── Commit ───────────────────────────────────────────────────────────────────

env.cr.commit()

# ── Report ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 55)
print("Step 01 — Demo Users")
print("=" * 55)
if created:
    print(f"  CREATED  ({len(created)}):")
    for login in created:
        print(f"    + {login}  [password: {DEMO_PASSWORD}]")
if skipped:
    print(f"  SKIPPED  ({len(skipped)}) — already exist:")
    for login in skipped:
        print(f"    ~ {login}")
print("=" * 55)
print("Done. Verify:")
print("  Settings > Users — look for Demo HR User and Demo Sales Manager")
print("  Try logging in as each user with password:", DEMO_PASSWORD)
print("=" * 55 + "\n")
