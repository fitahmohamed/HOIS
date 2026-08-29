# -*- coding: utf-8 -*-
{
    'name': "Requisitions for Construction",
    'version': "1.0",
    'summary': """This module allow your employees/users to create Purchase Requisitions.""",
    'description': """
    This module allowed Purchase requisition of employee.
    """,
    'category': 'Project',
    'author': 'Neoteric Hub',
    'company': 'Neoteric Hub',
    'live_test_url': '',
    'price': 875.00,
    'currency': 'USD',
    'website': 'https://www.neoterichub.com',
    'depends': ['nthub_constructions', 'nthub_project_requisitions'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/construction_project.xml',
        'views/project_task_views.xml',
        'views/purchase_requisition_views.xml',
        'views/purchase_order_views.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
