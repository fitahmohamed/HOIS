from odoo import models, fields, api
import json


class RenewalSettings(models.Model):
    _name = 'renewal.settings'
    _description = 'إعدادات التجديدات'

    name = fields.Char(default='الإعدادات الافتراضية')
    alert_level_1 = fields.Integer(string='مستوى تنبيه 1 (أيام)', default=30)
    alert_level_2 = fields.Integer(string='مستوى تنبيه 2 (أيام)', default=14)
    alert_level_3 = fields.Integer(string='مستوى تنبيه 3 (أيام)', default=7)
    alert_level_4 = fields.Integer(string='مستوى تنبيه 4 (أيام)', default=1)
    critical_days = fields.Integer(string='حد الحالة العاجلة (أيام)', default=7)
    warning_days = fields.Integer(string='حد التحذير (أيام)', default=30)
    notify_activity = fields.Boolean(string='إشعار بـ Activity', default=True)
    notify_email = fields.Boolean(string='إشعار بالبريد الإلكتروني', default=False)

    @api.model
    def _get_settings(self):
        settings = self.search([], limit=1)
        if not settings:
            settings = self.create({})
        return {
            'alert_levels': [
                settings.alert_level_1,
                settings.alert_level_2,
                settings.alert_level_3,
                settings.alert_level_4,
            ],
            'critical_days': settings.critical_days,
            'warning_days': settings.warning_days,
            'notify_activity': settings.notify_activity,
            'notify_email': settings.notify_email,
        }

    @api.model
    def get_or_create(self):
        settings = self.search([], limit=1)
        if not settings:
            settings = self.create({'name': 'الإعدادات الافتراضية'})
        return settings

    @api.model
    def action_open_settings(self):
        settings = self.get_or_create()
        return {
            'type': 'ir.actions.act_window',
            'name': 'إعدادات التجديدات',
            'res_model': 'renewal.settings',
            'res_id': settings.id,
            'view_mode': 'form',
            'target': 'new',
        }

