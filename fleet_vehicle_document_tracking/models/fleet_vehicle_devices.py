from odoo import fields, models


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    # GPS Registry
    gps_installed = fields.Boolean(string="GPS Installed", tracking=True)
    gps_id = fields.Char(string="GPS ID", tracking=True)
    gps_installation_date = fields.Date(string="GPS Installation Date")
    gps_provider = fields.Char(string="GPS Provider")
    gps_remark = fields.Text(string="GPS Remark")

    # Camera / PAS Registry
    camera_installed = fields.Boolean(string="Camera / PAS Installed", tracking=True)
    camera_id = fields.Char(string="Camera / PAS ID", tracking=True)
    camera_installation_date = fields.Date(string="Camera / PAS Installation Date")
    camera_provider = fields.Char(string="Camera / PAS Provider")
    camera_remark = fields.Text(string="Camera / PAS Remark")
