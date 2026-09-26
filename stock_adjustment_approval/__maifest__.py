{
    "name": "Stock Adjustment Approval",
    "version": "19.0.1.0.0",
    "category": "Inventory",
    "summary": "Require manager approval before applying inventory adjustments",
    "depends": ["stock", "mail"],
    "data": [
        "security/security.xml",
        "views/stock_quant_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}