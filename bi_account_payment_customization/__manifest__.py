# -*- coding: utf-8 -*-
{
    'name': "BI Account Payment Customization",
    'summary': "BI Account Payment Customization",
    'description': """ 
            This module make new changes to payments.
     """,
    'author': "BI Solutions Development Team",
    'category': 'Accounting',
    'version': '19.0.1.0.0',
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/inherit_account_payment_view.xml',
        'reports/payment_report.xml',
    ],
    'assets': {
        'web._assets_bootstrap': [
            'https://fonts.googleapis.com/css2?family=Almarai:wght@100;200;300;400;500;600;700;800;900&display=swap',
        ],
        'web.assets_frontend': [
            'bi_account_payment_customization/static/src/css/style.scss',
        ],
        'web.report_assets_common': [
            'bi_account_payment_customization/static/src/css/style.scss',
        ]
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'sequence': 1
}
