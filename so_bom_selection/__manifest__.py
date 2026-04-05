# -*- coding: utf-8 -*-
{
    'name': "Bill Of Material from Sale Order Line",
    'version': '19.0.1.0.1',
    'category': 'Manufacturing',
    'summary': 'Select the BOM in sale order line and generate the '
               'manufacturing order of components',
    'description': 'Select the Bill of Material of each product in '
                   'Sale Order Line. After confirmation of Sale Order, '
                   'Manufacturing Order of the components in the Bill of'
                   ' Material will be created automatically.',
    'author': 'omar',
    'depends': ['sale_management', 'mrp'],
    'data': [
        'views/sale_order_views.xml',
        'views/mrp_production_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
