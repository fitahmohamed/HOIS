# -*- coding: utf-8 -*-
{
    'name': "Construction Tenders",
    'version': "1.0",
    'summary': """
    Construction Tenders,
    Offer,
    Version,
    Project Management, 
    Construction, 
    Tenders, 
    Owner Contract, 
    Subcontractor, 
    Subcontractor Contract,
    Construction Management System (CMS), 
    Completion Request, 
    Tasks, delivery requests, 
    Work Breakdown Structure (WBS), 
    Work Breakdown Template (WBT),
    units, 
    jobs, 
    Dashboard,
    """,

    'description': """
    A system for managing the bidding process for construction projects.
    """,

    'category': 'Project',
    'author': 'Neoteric Hub',
    'company': 'Neoteric Hub',
    'live_test_url': '',
    'price': 800.00,
    'currency': 'USD',
    'website': 'https://www.neoterichub.com',

    'depends': ['nthub_constructions'],
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/tender_offer_sequence.xml',
        'data/tender_offer_version_sequence.xml',
        'wizards/new_version_wizard_view.xml',
        'views/top_sheet.xml',
        'views/tender_information.xml',
        'views/tender_offer_views.xml',
        'views/tender_offer_version_views.xml',
        'views/construction_project.xml',
        'views/project_tender.xml',
        'views/menu_views.xml',
        'report/offer_report.xml',
        'report/top_sheet_report.xml',

    ],

    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'images': ['static/description/banner.gif'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
