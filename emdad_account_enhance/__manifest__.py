# -*- coding: utf-8 -*-
{
    'name': "Emdad Account Enhance",

    'summary': """
      Enhance Default Invoice Document""",

    'description': """
         Enhance Default Invoice Document"
    """,

    'author': "Smart Beats",
    'website': "http://www.smartbeats-it.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '19.0.1.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'l10n_gcc_invoice', 'l10n_sa', 'l10n_sa_edi', 'sale', 'vs_sale_order_extension'],
    # always loaded
    'data': [
        'data/report_paperformat_data.xml',
        'reports/invoice_report_inherit.xml',
        'views/base_document_layout_views.xml',
        'views/account_move_views.xml',
        'views/account_move_reversal_views.xml',
    ],
    # only loaded in demonstration mode
    
}