from datetime import timedelta

from odoo import Command, _, api, fields, models

from .document_common import (
    DOC_FIELD_MAP, DOC_TYPES, INSURANCE_TYPES, PREFIXES, STATUS_SELECTION, days_left, get_status,
)

History = "fleet.vehicle.document.history"


def _history(doc_type, string):
    return fields.One2many(History, "vehicle_id", domain=[("doc_type", "=", doc_type)], string=string)


def _status(string):
    return fields.Selection(STATUS_SELECTION, string=string, compute="_compute_doc_status", store=True)


def _remaining(string):
    return fields.Integer(string=string, compute="_compute_doc_remaining_days")


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    # ------------------------------------------------------------------ Vehicle Registration
    registration_number = fields.Char(string="Vehicle Registration Number", tracking=True)
    registration_file = fields.Binary(string="Registration File", attachment=True)
    registration_file_name = fields.Char()
    registration_note = fields.Text(string="Registration Note")
    registration_status = _status("Registration Status")
    registration_issue_date = fields.Date(string="Registration Issue Date")
    registration_expiry_date = fields.Date(string="Registration Expiry Date", tracking=True)
    registration_remaining_days = _remaining("Registration Remaining Days")
    registration_history_ids = _history("registration", "Vehicle Registration History")

    # ------------------------------------------------------------------ Insurance Register
    insurance_company = fields.Char(string="Insurance Company")
    insurance_type = fields.Selection(INSURANCE_TYPES, string="Insurance Type")
    insurance_policy_number = fields.Char(string="Policy Number", tracking=True)
    insurance_amount = fields.Monetary(string="Insurance Amount", currency_field="currency_id")
    insurance_file = fields.Binary(string="Insurance File", attachment=True)
    insurance_file_name = fields.Char()
    insurance_note = fields.Text(string="Insurance Note")
    insurance_status = _status("Insurance Status")
    insurance_issue_date = fields.Date(string="Insurance Issue Date")
    insurance_expiry_date = fields.Date(string="Insurance Expiry Date", tracking=True)
    insurance_remaining_days = _remaining("Insurance Remaining Days")
    insurance_history_ids = _history("insurance", "Insurance Register History")

    # ------------------------------------------------------------------ MVPI
    mvpi_number = fields.Char(string="MVPI Number", tracking=True)
    mvpi_file = fields.Binary(string="MVPI File", attachment=True)
    mvpi_file_name = fields.Char()
    mvpi_note = fields.Text(string="MVPI Note")
    mvpi_status = _status("MVPI Status")
    mvpi_issue_date = fields.Date(string="MVPI Issue Date")
    mvpi_expiry_date = fields.Date(string="MVPI Expiry Date", tracking=True)
    mvpi_remaining_days = _remaining("MVPI Remaining Days")
    mvpi_history_ids = _history("mvpi", "MVPI History")

    # ------------------------------------------------------------------ Vehicle Authorization
    authorization_number = fields.Char(string="Authorization Number", tracking=True)
    authorization_driver_id = fields.Many2one("res.partner", string="Authorized Driver")
    authorization_file = fields.Binary(string="Authorization File", attachment=True)
    authorization_file_name = fields.Char()
    authorization_note = fields.Text(string="Authorization Note")
    authorization_status = _status("Authorization Status")
    authorization_issue_date = fields.Date(string="Authorization Issue Date")
    authorization_expiry_date = fields.Date(string="Authorization Expiry Date", tracking=True)
    authorization_remaining_days = _remaining("Authorization Remaining Days")
    authorization_history_ids = _history("authorization", "Vehicle Authorization History")

    # ------------------------------------------------------------------ Operation Card
    operation_card_number = fields.Char(string="Operation Card Number", tracking=True)
    operation_card_file = fields.Binary(string="Operation Card File", attachment=True)
    operation_card_file_name = fields.Char()
    operation_card_note = fields.Text(string="Operation Card Note")
    operation_card_status = _status("Operation Card Status")
    operation_card_issue_date = fields.Date(string="Operation Card Issue Date")
    operation_card_expiry_date = fields.Date(string="Operation Card Expiry Date", tracking=True)
    operation_card_remaining_days = _remaining("Operation Card Remaining Days")
    operation_card_history_ids = _history("operation_card", "Operation Card History")

    # ------------------------------------------------------------------ All history (smart button)
    document_history_ids = fields.One2many(History, "vehicle_id", string="Renewal History")
    document_history_count = fields.Integer(compute="_compute_document_history_count")

    # ------------------------------------------------------------------ Computes
    @api.depends(*[f"{p}_expiry_date" for p in PREFIXES])
    def _compute_doc_remaining_days(self):
        today = fields.Date.today()
        for vehicle in self:
            for prefix in PREFIXES:
                vehicle[f"{prefix}_remaining_days"] = days_left(vehicle[f"{prefix}_expiry_date"], today)

    @api.depends(*[f"{p}_expiry_date" for p in PREFIXES])
    def _compute_doc_status(self):
        settings = self.env["renewal.settings"].sudo()._get_settings()
        today = fields.Date.today()
        for vehicle in self:
            for prefix in PREFIXES:
                vehicle[f"{prefix}_status"] = get_status(vehicle[f"{prefix}_expiry_date"], settings, today)

    def _compute_document_history_count(self):
        data = self.env[History]._read_group(
            [("vehicle_id", "in", self.ids)], ["vehicle_id"], ["__count"])
        counts = {vehicle.id: count for vehicle, count in data}
        for vehicle in self:
            vehicle.document_history_count = counts.get(vehicle.id, 0)

    @api.model
    def _documents_domain(self):
        return ["|"] * (len(PREFIXES) - 1) + [(f"{p}_expiry_date", "!=", False) for p in PREFIXES]

    @api.model
    def _recompute_document_status(self):
        """Statuses depend on today's date and on the settings: recompute them."""
        vehicles = self.sudo().with_context(active_test=False).search(self._documents_domain())
        fnames = [f"{p}_status" for p in PREFIXES]
        for fname in fnames:
            self.env.add_to_compute(self._fields[fname], vehicles)
        vehicles._recompute_recordset(fnames)
        self.env[History]._recompute_document_status()

    # ------------------------------------------------------------------ Alerts (renewal_tracker settings)
    @api.model
    def _cron_vehicle_document_alerts(self):
        self._recompute_document_status()
        settings = self.env["renewal.settings"].sudo()._get_settings()
        alert_levels = settings.get("alert_levels", [30, 14, 7, 1])
        today = fields.Date.today()
        labels = dict(DOC_TYPES)
        for vehicle in self.sudo().search(self._documents_domain()):
            for prefix in PREFIXES:
                expiry = vehicle[f"{prefix}_expiry_date"]
                if not expiry:
                    continue
                left = (expiry - today).days
                if left < 0:
                    vehicle._document_alert(prefix, labels[prefix], left, expiry, settings, expired=True)
                elif left in alert_levels:
                    vehicle._document_alert(prefix, labels[prefix], left, expiry, settings)

    def _document_alert_summaries(self, label):
        return (f"تجديد قريب: {label}", f"وثيقة منتهية: {label}")

    def _document_alert_users(self, prefix, settings):
        """Users chosen in the renewal settings; otherwise the fleet manager of the vehicle."""
        self.ensure_one()
        users = self.env["res.users"].sudo().browse(settings.get("notify_user_ids") or []).exists()
        if users:
            return users
        if self.manager_id:
            return self.manager_id
        last = self.env[History].sudo().search(
            [("vehicle_id", "=", self.id), ("doc_type", "=", prefix)], limit=1)
        return last.user_id or self.env.ref("base.user_admin")

    def _document_alert(self, prefix, label, left, expiry, settings, expired=False):
        self.ensure_one()
        users = self._document_alert_users(prefix, settings)
        upcoming, expired_summary = self._document_alert_summaries(label)
        vehicle_name = self.display_name
        if expired:
            summary = expired_summary
            note = f"انتهت صلاحية {label} للمركبة {vehicle_name} منذ {abs(left)} يوم. يرجى التجديد فوراً."
            deadline = fields.Date.today()
        else:
            summary = upcoming
            note = f"ستنتهي صلاحية {label} للمركبة {vehicle_name} خلال {left} يوم بتاريخ {expiry}."
            deadline = fields.Date.today() + timedelta(days=min(left, 3))

        if settings.get("notify_activity", True):
            for user in users:
                exists = self.env["mail.activity"].sudo().search_count([
                    ("res_model", "=", "fleet.vehicle"),
                    ("res_id", "=", self.id),
                    ("summary", "=", summary),
                    ("user_id", "=", user.id),
                ], limit=1)
                if not exists:
                    self.activity_schedule(
                        act_type_xmlid="mail.mail_activity_data_todo",
                        summary=summary, note=note, date_deadline=deadline, user_id=user.id,
                    )
        partners = users.partner_id.filtered("email")
        if settings.get("notify_email") and not expired and partners:
            template = self.env.ref(
                "fleet_vehicle_document_tracking.email_template_vehicle_document_alert",
                raise_if_not_found=False)
            if template:
                template.with_context(
                    doc_label=label, days_left=left, expiry_date=expiry,
                    responsible_name=users[0].name if len(users) == 1 else "",
                ).send_mail(
                    self.id, force_send=True,
                    email_values={"recipient_ids": [Command.set(partners.ids)], "email_to": False},
                )

    def _close_document_alerts(self, prefix):
        label = dict(DOC_TYPES)[prefix]
        self.env["mail.activity"].sudo().search([
            ("res_model", "=", "fleet.vehicle"),
            ("res_id", "in", self.ids),
            ("summary", "in", list(self._document_alert_summaries(label))),
        ]).action_done()

    # ------------------------------------------------------------------ First entry -> history line
    @api.model_create_multi
    def create(self, vals_list):
        vehicles = super().create(vals_list)
        if not self.env.context.get("skip_initial_document_history"):
            for vehicle, vals in zip(vehicles, vals_list):
                vehicle._sync_initial_document_history(self._document_prefixes_in(vals))
        return vehicles

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_initial_document_history"):
            prefixes = self._document_prefixes_in(vals)
            if prefixes:
                for vehicle in self:
                    vehicle._sync_initial_document_history(prefixes)
        return res

    @api.model
    def _document_prefixes_in(self, vals):
        return [p for p in PREFIXES if set(DOC_FIELD_MAP[p].values()) & set(vals)]

    def _document_snapshot(self, prefix):
        self.ensure_one()
        values = {}
        for generic, field_name in DOC_FIELD_MAP[prefix].items():
            value = self[field_name]
            if isinstance(value, models.BaseModel):
                value = value.id
            values[generic] = value
        return values

    def _sync_initial_document_history(self, prefixes):
        """The first time a document is filled in, log it as an "initial" history line.
        Until the first renewal, direct edits keep that initial line up to date."""
        self.ensure_one()
        lines_model = self.env[History].sudo()
        for prefix in prefixes:
            snapshot = self._document_snapshot(prefix)
            if not any(v for k, v in snapshot.items() if k != "file_name"):
                continue
            lines = lines_model.search([("vehicle_id", "=", self.id), ("doc_type", "=", prefix)])
            if not lines:
                lines_model.create(dict(
                    snapshot, vehicle_id=self.id, doc_type=prefix,
                    entry_type="initial", user_id=self.env.user.id,
                ))
            elif len(lines) == 1 and lines.entry_type == "initial":
                lines.write(snapshot)

    # ------------------------------------------------------------------ Actions
    def action_open_document_renewal(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Renewal"),
            "res_model": "fleet.vehicle.document.renewal",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_vehicle_id": self.id,
                "default_doc_type": self.env.context.get("doc_type"),
            },
        }

    def action_open_document_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Renewal History"),
            "res_model": History,
            "view_mode": "list,form",
            "views": [
                (self.env.ref("fleet_vehicle_document_tracking.view_fleet_vehicle_document_history_all_list").id, "list"),
                (False, "form"),
            ],
            "domain": [("vehicle_id", "=", self.id)],
            "context": {"default_vehicle_id": self.id, "create": False},
        }
