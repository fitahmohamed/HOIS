{
    "name": "Employee Document Tracking",
    "version": "19.0.1.0.0",
    "summary": "Track Passport, Iqama, Driving License, Driver Card and Medical Insurance "
               "on employees with renewal wizard and renewal history",
    "category": "Human Resources/Employees",
    "author": "VS/HOIS",
    "license": "LGPL-3",
    "depends": ["hr"],
    "data": [
        "security/ir.model.access.csv",
        "views/hr_employee_document_history_views.xml",
        "wizard/hr_employee_document_renewal_views.xml",
        "views/hr_employee_views.xml",
    ],
    "installable": True,
    "application": False,
}
