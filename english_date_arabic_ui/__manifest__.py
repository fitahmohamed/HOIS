{
    "name": "English Dates with Arabic UI",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "summary": "Display dates in English while keeping the Odoo interface Arabic",
    "depends": [
        "web",
    ],
    "assets": {
        "web.assets_backend": [
            "english_date_arabic_ui/static/src/js/english_date.js",
            "english_date_arabic_ui/static/src/scss/english_date.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}