{
    "name": "Employee Document Tracking",
    "version": "19.0.1.2.0",
    "summary": "Track Passport, Iqama, Driving License, Driver Card and Medical Insurance "
               "on employees with renewal wizard, renewal history and automatic statuses "
               "linked to Renewal Tracker",
    "category": "Human Resources/Employees",
    "author": "VS/HOIS",
    "license": "LGPL-3",
    "depends": ["hr", "renewal_tracker"],
    "data": [
        "security/renewal_security.xml",
        "security/ir.model.access.csv",
        "data/mail_template_data.xml",
        "views/hr_employee_document_history_views.xml",
        "wizard/hr_employee_document_renewal_views.xml",
        "views/hr_employee_views.xml",
        "views/employee_renewal_views.xml",
        "views/renewal_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
