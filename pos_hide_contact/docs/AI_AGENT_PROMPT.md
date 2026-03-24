# Copy/Paste Prompt for AI Coding Agent

Role: You are an expert Odoo 19 Technical Developer.

Task: Write the complete, production-ready code for a minimal Odoo 19 module that filters which customers are loaded into the Point of Sale (POS) session.

Context & Requirements:
- Objective: Provide the ability to mark specific partners/clients as available or unavailable in the POS system. Only partners/customers marked as available will be displayed in the POS partner selection screen, streamlining the process for cashiers and preventing them from selecting suppliers or incorrect contacts.
- Technical Name: pos_hide_contact.
- Version: Odoo 19.0 (Compatible with Community and Enterprise).
- Constraint: The entire module must be highly optimized and extremely lightweight, aiming for a total of approximately 33 lines of code. Do not use any frontend JavaScript patching; rely entirely on backend domain filtering.

Technical Specifications & Mapping:
1. __manifest__.py: Create a standard manifest depending on base and point_of_sale.
2. Model Modification (res.partner): Inherit the res.partner model and add a single boolean field: available_in_pos (String: "Available in POS", Default: False).
3. View Modification (res.partner): Inherit the base.view_partner_form view. Use an XPath expression to cleanly inject the available_in_pos checkbox into the form (preferably in the "Point of Sale" tab or main contact details).
4. Logic Override (pos.session): Inherit the pos.session model. Override the _loader_params_res_partner(self) method. Call super() to get the original dictionary of parameters, and append ('available_in_pos', '=', True) to the search domain list inside that dictionary before returning it.

Output Generation:
Please provide the exact file directory structure and the complete code for the following files:
1. __init__.py (Root)
2. __manifest__.py
3. models/__init__.py
4. models/res_partner.py
5. models/pos_session.py
6. views/res_partner_views.xml

Keep the code as concise as possible to respect the ~33 lines of code constraint. Include brief comments explaining the pos.session override logic.
