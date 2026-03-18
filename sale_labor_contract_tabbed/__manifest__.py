{
    "name": "Sale Labor Contract Tabbed",
    "summary": "Labor outsourcing calculations on sales order lines",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "author": "Bayet Elholol",
    "license": "LGPL-3",
    "depends": ["sale", "product"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/labor_rules_config_views.xml",
        "views/sale_order_line_views.xml",
        "views/sale_order_views.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
    "installable": True,
    "application": False,
}
