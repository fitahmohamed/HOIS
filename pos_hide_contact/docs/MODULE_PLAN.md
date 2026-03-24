# Module Plan: pos_hide_contact

Date: 2026-03-24
Target Version: Odoo 19.0 (Community and Enterprise)
Type: Minimal backend-only POS customer filter module

## 1) Goal

Allow only approved customers to appear in POS customer selection by adding a boolean flag on contacts and filtering POS partner loader data by that flag.

## 2) Constraints

- Keep module lightweight and minimal.
- No frontend JavaScript patching.
- Use backend domain filtering only.
- Expected total code size is very small (around 33 lines).

## 3) Required Files

- __init__.py
- __manifest__.py
- models/__init__.py
- models/res_partner.py
- models/pos_session.py
- views/res_partner_views.xml

## 4) Functional Scope

- Add field on res.partner:
  - available_in_pos (Boolean, default False)
- Expose field in partner form view.
- Override POS partner loader params to append:
  - ('available_in_pos', '=', True)

## 5) Technical Mapping

### Manifest

- Depends on:
  - base
  - point_of_sale
- Data files:
  - views/res_partner_views.xml

### Partner Model

- Inherit res.partner
- Add available_in_pos = fields.Boolean(string="Available in POS", default=False)

### Partner Form View

- Inherit base.view_partner_form
- Add checkbox using XPath into a suitable section (POS area or contact details block)

### POS Session Logic

- Inherit pos.session
- Override _loader_params_res_partner(self)
- Call super() and update domain list:
  - append ('available_in_pos', '=', True)

## 6) Acceptance Criteria

- Contacts with available_in_pos = False do not appear in POS partner selector.
- Contacts with available_in_pos = True appear normally.
- No POS frontend override is used.
- Module installs cleanly on Odoo 19.

## 7) Quick Validation Steps

1. Install module in a test database.
2. Create two contacts, mark one as Available in POS.
3. Open POS and verify only the flagged contact is loaded/searchable.
4. Unflag contact and re-open POS session to confirm exclusion.
