{
    'name': 'متابعة التجديدات',
    'version': '19.0.1.0.0',
    'category': 'Operations',
    'summary': 'متابعة تجديد رخص السيارات وأوراق الموظفين',
    'description': """
    """,
    'author': 'Custom',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'data/mail_template_data.xml',
        'views/renewal_document_views.xml',
        'views/renewal_settings_views.xml',
        'views/renewal_dashboard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'renewal_tracker/static/src/css/renewal_tracker.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
