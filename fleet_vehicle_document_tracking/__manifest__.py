{
    "name": "Fleet Vehicle Document Tracking",
    "version": "19.0.1.1.0",
    "summary": "Track Vehicle Registration, Insurance, MVPI, Vehicle Authorization and Operation Card "
               "on vehicles with renewal wizard, renewal history and automatic statuses "
               "linked to Renewal Tracker",
    "category": "Human Resources/Fleet",
    "author": "VS/HOIS",
    "license": "LGPL-3",
    "depends": ["fleet", "renewal_tracker"],
    "data": [
        "security/ir.model.access.csv",
        "data/mail_template_data.xml",
        "views/fleet_vehicle_document_history_views.xml",
        "wizard/fleet_vehicle_document_renewal_views.xml",
        "views/fleet_vehicle_views.xml",
        "views/vehicle_renewal_views.xml",
    ],
    "installable": True,
    "application": False,
}
