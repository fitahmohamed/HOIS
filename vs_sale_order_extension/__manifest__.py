{
    "name": "VS Sale Order Extension",
    "version": "19.0.1.0.0",
    "summary": "Additional sales order references, statuses, and analytic helpers",
    "category": "Sales",
    "author": "VS/HOIS",
    "license": "LGPL-3",
    "depends": [
        "sale_management",
        "sale_renting",
        "sale_stock",
        "analytic",
    ],
    "data": [
        "views/sale_order_views.xml",
        "views/rental_order_views.xml",
    ],
    "installable": True,
    "application": False,
}