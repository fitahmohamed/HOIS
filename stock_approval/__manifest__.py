{
    "name": "Stock Inventory Approval",
    "version": "19.0.1.0.0",
    "category": "Inventory",
    "summary": "Require approval before applying inventory adjustments, with a reason log per line",
    "depends": ["stock", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizard/stock_quant_reason_wizard_views.xml",
        "views/stock_quant_views.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'stock_approval/static/src/js/activity_controller_patch.js',
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}