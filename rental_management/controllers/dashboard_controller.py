# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
"""
Dashboard Data Controller
Dedicated controller for serving all dashboard data via JSON endpoints.
Uses direct SQL for heavy aggregations to ensure minimal query count and fast loading.
"""
import logging
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


TYPE_LABELS = {
    'land':        'Land',
    'residential': 'Residential',
    'commercial':  'Commercial',
    'industrial':  'Industrial',
}


MAINTENANCE_TYPE = {
    'corrective': 'Corrective',
    'preventive': 'Preventive',
}

# Models whose chatter should populate the live activity feed.
ACTIVITY_MODELS = (
    'tenancy.details',
    'property.details',
    'property.vendor',
    'maintenance.request',
    'rent.invoice',
    'account.move',
    'crm.lead',
)

# Human labels for each model surfaced in the activity feed.
ACTIVITY_MODEL_LABELS = {
    'tenancy.details':     'Rent Contract',
    'property.details':    'Property',
    'property.vendor':     'Sale Contract',
    'maintenance.request': 'Maintenance',
    'rent.invoice':        'Rent Invoice',
    'account.move':        'Invoice',
    'crm.lead':            'Lead',
}

# How `mail.message.message_type` maps to the visual kind used by the UI.
ACTIVITY_KIND_BY_MESSAGE_TYPE = {
    'comment':      'note',
    'auto_comment': 'system',
    'notification': 'system',
}


def broker_sale_commission_expr(alias=None):
    """
    Returns the SQL expression for broker_final_commission.
    Mirrors _compute_broker_final_commission logic.
    Pass a table alias if columns are ambiguous in JOINs.
    e.g. broker_sale_commission_expr('pv') → CASE WHEN pv.is_any_broker ...
    """
    p = f"{alias}." if alias else ""
    return f"""
        CASE
            WHEN {p}is_any_broker = TRUE THEN
                CASE
                    WHEN {p}commission_type = 'p'
                    THEN {p}sale_price * {p}broker_commission_percentage / 100.0
                    ELSE {p}broker_commission
                END
            ELSE 0.0
        END
    """.strip()


def broker_rent_commission_expr(alias=None):
    """
    Returns the SQL expression for rent broker commission.
    Mirrors _compute_broker_commission logic.
    Pass a table alias if columns are ambiguous in JOINs.
    e.g. broker_rent_commission_expr('td') → CASE WHEN td.is_any_broker ...
    """
    p = f"{alias}." if alias else ""
    month_expr = f"(SELECT month FROM contract_duration WHERE id = {p}duration_id)"
    return f"""
        CASE
            WHEN {p}is_any_broker = TRUE THEN
                CASE
                    WHEN {p}rent_type = 'once' THEN
                        CASE
                            WHEN {p}commission_type = 'f' THEN {p}broker_commission
                            WHEN {p}commission_type = 'p' THEN {p}broker_commission_percentage * {p}total_rent / 100.0
                            ELSE 0.0
                        END
                    WHEN {p}rent_type = 'e_rent' THEN
                        CASE
                            WHEN {p}commission_type = 'f' THEN {p}broker_commission * COALESCE({month_expr}, 0)
                            WHEN {p}commission_type = 'p' THEN {p}broker_commission_percentage * {p}total_rent / 100.0 * COALESCE({month_expr}, 0)
                            ELSE 0.0
                        END
                    ELSE 0.0
                END
            ELSE 0.0
        END
    """.strip()


def format_money(amount):
    """
    Company-currency-aware money formatter.

    INR: lakh (L) / crore (Cr) suffixes.
    Other currencies: K / M / B suffixes.
    Symbol position respects currency.position ('before'/'after').
    """
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        amount = 0.0

    env = request.env
    currency = env.company.currency_id
    symbol = currency.symbol or ''
    position = currency.position or 'before'
    is_inr = (currency.name or '').upper() == 'INR'

    abs_amt = abs(amount)
    if is_inr:
        if abs_amt >= 10_000_000:
            formatted = f"{amount / 10_000_000:.2f} Cr"
        elif abs_amt >= 100_000:
            formatted = f"{amount / 100_000:.2f} Lakh"
        else:
            formatted = f"{amount:,.0f}"
    else:
        if abs_amt >= 1_000_000_000:
            formatted = f"{amount / 1_000_000_000:.2f} Billion"
        elif abs_amt >= 1_000_000:
            formatted = f"{amount / 1_000_000:.2f} Million"
        elif abs_amt >= 1_000:
            formatted = f"{amount / 1_000:.1f}K"
        else:
            formatted = f"{amount:,.0f}"

    return f"{symbol} {formatted}" if position == 'before' else f"{formatted} {symbol}"


def _resolve_translated(val):
    """
    Safely extract a display string from an Odoo 17 translated field.
    Handles: plain string, jsonb dict, None.
    Priority: user's active language → en_US → first available value.
    """
    if not val:
        return ''
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        # Try the user's active UI language first
        user_lang = request.env.lang or request.env.context.get('lang') or 'en_US'
        return (
            val.get(user_lang)          # e.g. 'fr_FR', 'ar_SA', 'hi_IN'
            or val.get('en_US')         # universal fallback
            or next(iter(val.values()), '')  # any value if en_US also missing
        )
    return str(val)


class RentalDashboardController(http.Controller):
    """Dedicated controller for the rental management dashboard.
    All endpoints return JSON and use direct SQL for performance.
    """

    # ──────────────────────────────────────────────────────────────────────────
    # THEME ENDPOINT
    # ──────────────────────────────────────────────────────────────────────────

    @http.route('/rental/dashboard/theme', type='json', auth='user', methods=['POST'])
    def get_dashboard_theme(self):
        """Return the currently active dashboard theme from ir.config_parameter."""
        ICP = request.env['ir.config_parameter'].sudo()
        return {
            'theme': ICP.get_param('rental_management.dashboard_theme', default='Teal'),
        }

    @http.route('/rental/dashboard/theme/save', type='json', auth='user', methods=['POST'])
    def save_dashboard_theme(self, theme_name):
        """Persist the selected theme in ir.config_parameter."""
        ICP = request.env['ir.config_parameter'].sudo()
        ICP.set_param('rental_management.dashboard_theme', theme_name)
        return {'success': True}

    # ──────────────────────────────────────────────────────────────────────────
    # MASTER DATA ENDPOINT — single call loads all dashboard data
    # ──────────────────────────────────────────────────────────────────────────

    @http.route('/rental/dashboard/data', type='json', auth='user', methods=['POST'])
    def get_dashboard_data(self):
        """
        Single endpoint that fetches all dashboard data in one round-trip.
        Combines results from focused SQL queries into a single JSON response.
        """
        try:
            return {
                'currency': self._get_currency_info(),
                'kpis': self._get_kpis(),
                'sankey': self._get_sankey(),
                'radar': self._get_radar(),
                'forecast': self._get_forecast(),
                'occupancy_gauge': self._get_occupancy_gauge(),
                'revenue_mix': self._get_revenue_mix(),
                'top_properties': self._get_top_properties(),
                'overdue_invoices': self._get_overdue_invoices(),
                'right_panel': self._get_right_panel(),
                'upcoming_events': self._get_upcoming_events(),
                'activity_feed': self._get_activity_feed(),
                'maintenance_status': self._get_maintenance_status(),
                'sidebar_glance': self._get_sidebar_glance(),
                'leads': self._get_leads(),
            }
        except Exception as e:
            _logger.exception("Dashboard data fetch error: %s", e)
            return {'error': str(e)}

    def _get_currency_info(self):
        """Company currency metadata consumed by the JS formatter."""
        currency = request.env.company.currency_id
        return {
            'id': currency.id,
            'name': currency.name,
            'symbol': currency.symbol or '',
            'position': currency.position or 'before',
            'decimals': currency.decimal_places,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE-SPECIFIC ENDPOINTS (lazy-loaded when user navigates to that page)
    # ──────────────────────────────────────────────────────────────────────────

    @http.route('/rental/dashboard/properties', type='json', auth='user', methods=['POST'])
    def get_properties_page(self):
        """
        Properties page data.

        The full property grid has been replaced with a focused
        "Recent Properties" card — properties created in the last 3 days.
        The heavy grid remains available via the `Open in Odoo` action so
        power users retain access without bloating the dashboard response.
        """
        return {
            'stat_bar':          self._get_property_stat_bar(),
            'occupancy_by_type': self._get_occupancy_by_type(),
            'portfolio_mix':     self._get_portfolio_mix(),
            'recent_properties': self._get_recent_properties(),
        }

    @http.route('/rental/dashboard/rent', type='json', auth='user', methods=['POST'])
    def get_rent_page(self):
        """
        Data for the unified "Rental & Contracts" page.

        Merges the old /rent and /contracts responses so the UI can show
        rent operations (collection, active tenants) alongside the
        contract lifecycle (timeline, full contract list) on one screen.
        """
        return {
            'stat_bar':           self._get_rental_contracts_stat_bar(),
            'monthly_collection': self._get_monthly_rent_collection(),
            'collection_by_type': self._get_collection_by_type(),
            'rent_table':         self._get_rent_table(),
            'gantt':              self._get_contracts_gantt(),
            'contract_list':      self._get_contract_list(),
        }

    # Kept for backwards-compatibility with any deep links; serves identical data.
    @http.route('/rental/dashboard/rent_contracts', type='json', auth='user', methods=['POST'])
    def get_rental_contracts_page(self):
        return self.get_rent_page()

    @http.route('/rental/dashboard/sales', type='json', auth='user', methods=['POST'])
    def get_sales_page(self):
        """Data for the Sales page."""
        return {
            'stat_bar': self._get_sales_stat_bar(),
            'funnel': self._get_sales_funnel(),
            'sales_by_type': self._get_sales_by_type(),
            'sales_table': self._get_sales_table(),
        }

    @http.route('/rental/dashboard/maintenance', type='json', auth='user', methods=['POST'])
    def get_maintenance_page(self):
        """Data for the Maintenance page."""
        return {
            'stat_bar': self._get_maintenance_stat_bar(),
            'ticket_trends': self._get_ticket_trends(),
            'by_category': self._get_maintenance_by_category(),
            'maintenance_table': self._get_maintenance_table(),
        }

    @http.route('/rental/dashboard/contracts', type='json', auth='user', methods=['POST'])
    def get_contracts_page(self):
        """Data for the Contracts page."""
        return {
            'stat_bar': self._get_contracts_stat_bar(),
            'gantt': self._get_contracts_gantt(),
            'contract_list': self._get_contract_list(),
        }

    @http.route('/rental/dashboard/brokers', type='json', auth='user', methods=['POST'])
    def get_brokers_page(self):
        """Data for the Brokers page."""
        return {
            'stat_bar': self._get_brokers_stat_bar(),
            'broker_performance': self._get_broker_performance(),
            'commission_breakdown': self._get_commission_breakdown(),
            'broker_table': self._get_broker_table(),
        }

    @http.route('/rental/dashboard/map', type='json', auth='user', methods=['POST'])
    def get_map_page(self):
        """Data for the Map page — property geo coordinates and regional data."""
        return {
            'properties': self._get_map_properties(),
            'regional': self._get_regional_data(),
            'city_distribution': self._get_city_distribution(),
            'density': self._get_density_data(),
            'city_trend': self._get_city_trend(),
        }

    def _lang_extract(self, col, alias=None):
        """
        Returns a SQL expression that extracts the correct translation
        from an Odoo 17 jsonb translated field column.

        Priority: user's active lang → en_US → first jsonb value.

        Usage:
            self._lang_extract('p.name')        → full expression string
            self._lang_extract('name', 'p')     → same, alias applied
        """
        # Build full column reference
        col_ref = f"{alias}.{col}" if alias and '.' not in col else col

        # Get active language from context (e.g. 'fr_FR', 'hi_IN', 'en_US')
        lang = (
                request.env.lang
                or request.env.context.get('lang')
                or 'en_US'
        )

        if lang == 'en_US':
            # Simple path — no COALESCE needed
            return f"({col_ref} ->>'en_US')"

        # Try user lang first, fall back to en_US, then any first value
        return f"""COALESCE(
            NULLIF({col_ref} ->>'{lang}', ''),
            NULLIF({col_ref} ->>'en_US', ''),
            ({col_ref}::jsonb -> (SELECT key FROM jsonb_object_keys({col_ref}::jsonb) AS t(key) LIMIT 1))::text
        )"""

    # ──────────────────────────────────────────────────────────────────────────
    # KPI HELPERS  (direct SQL for speed)
    # ──────────────────────────────────────────────────────────────────────────

    def _get_kpis(self):
        """
        Returns the 6 main KPI cards.
        Single SQL per KPI group to avoid N+1 ORM calls.
        """
        cr = request.env.cr

        # ── Occupancy Rate ──────────────────────────────────────────────────
        cr.execute("""
                   SELECT COUNT(*) FILTER (WHERE stage = 'on_lease')   AS rented, COUNT(*) FILTER (WHERE stage = 'sale')        AS in_sale, COUNT(*) FILTER (WHERE stage = 'available')   AS available, COUNT(*) AS total
                   FROM property_details
                   """)
        prop = cr.dictfetchone() or {}
        total_props = prop.get('total', 0) or 1
        occupied = (prop.get('rented', 0) or 0) + (prop.get('in_sale', 0) or 0)
        occupancy_rate = round(occupied / total_props * 100, 1)

        # ── Revenue (current month invoices) ─────────────────────────────────
        today = date.today()
        first_of_month = today.replace(day=1)
        cr.execute("""
                   SELECT COALESCE(SUM(amount_untaxed_signed), 0) AS revenue
                   FROM account_move
                   WHERE move_type IN ('out_invoice')
                     AND state = 'posted'
                     AND invoice_date >= %s
                     AND invoice_date <= %s
                   """, (first_of_month, today))
        rev_row = cr.fetchone()
        revenue_curr = float(rev_row[0]) if rev_row else 0.0

        # Previous month for trend
        prev_first = (first_of_month - timedelta(days=1)).replace(day=1)
        prev_last = first_of_month - timedelta(days=1)
        cr.execute("""
                   SELECT COALESCE(SUM(amount_untaxed_signed), 0) AS revenue
                   FROM account_move
                   WHERE move_type = 'out_invoice'
                     AND state = 'posted'
                     AND invoice_date >= %s
                     AND invoice_date <= %s
                   """, (prev_first, prev_last))
        rev_prev_row = cr.fetchone()
        revenue_prev = float(rev_prev_row[0]) if rev_prev_row and rev_prev_row[0] else 1.0
        rev_trend = round((revenue_curr - revenue_prev) / revenue_prev * 100, 1) if revenue_prev else 0

        # ── Active Rent Contracts ─────────────────────────────────────────────
        cr.execute("""
                   SELECT COUNT(*) AS running
                   FROM tenancy_details
                   WHERE contract_type = 'running_contract'
                   """)
        contracts_row = cr.dictfetchone() or {}
        active_contracts = contracts_row.get('running', 0) or 0

        # ── Renewals Due (next 60 days) ───────────────────────────────────────
        due_cutoff = today + timedelta(days=60)
        cr.execute("""
                   SELECT COUNT(*)
                   FROM tenancy_details
                   WHERE contract_type = 'running_contract'
                     AND duration_end_date BETWEEN %s AND %s
                   """, (today, due_cutoff))
        renewals_row = cr.fetchone()
        renewals_due = int(renewals_row[0]) if renewals_row else 0

        # ── Churn (exits last 30 days) ────────────────────────────────────────
        cr.execute("""
                   SELECT COUNT(*)
                   FROM tenancy_details
                   WHERE contract_type IN ('cancel_contract', 'close_contract', 'expire_contract')
                     AND write_date >= NOW() - INTERVAL '30 days'
                   """)
        churn_row = cr.fetchone()
        churned = int(churn_row[0]) if churn_row else 0
        churn_rate = round(churned / total_props * 100, 1) if total_props else 0

        # ── Churn Sparkline (last 9 months, month-by-month) ───────────────────
        cr.execute("""
                   WITH months AS (SELECT generate_series(
                                                  DATE_TRUNC('month', NOW()) - INTERVAL '8 months',
                                                  DATE_TRUNC('month', NOW()),
                                                  INTERVAL '1 month'
                                          ) AS month_start),
                        monthly_churn AS (SELECT DATE_TRUNC('month', write_date) AS month_start,
                                                 COUNT(*)                        AS churned_count
                                          FROM tenancy_details
                                          WHERE
                                              contract_type IN ('cancel_contract', 'close_contract', 'expire_contract')
                                            AND write_date >= NOW() - INTERVAL '9 months'
                   GROUP BY DATE_TRUNC('month', write_date)
                       )
                   SELECT m.month_start,
                          COALESCE(mc.churned_count, 0) AS churned_count
                   FROM months m
                            LEFT JOIN monthly_churn mc ON m.month_start = mc.month_start
                   ORDER BY m.month_start ASC
                   """)
        churn_spark_rows = cr.fetchall()

        # Build sparkline as churn rates (churned / total_props * 100)
        churn_spark = [
            round(int(row[1]) / total_props * 100, 1) if total_props else 0
            for row in churn_spark_rows
        ]

        # ── Rental Yield (annualised rent / property value approx) ────────────
        cr.execute("""
                   SELECT TO_CHAR(DATE_TRUNC('month', rc.start_date), 'Mon YYYY') AS month,
                COALESCE(SUM(
                    CASE p.rent_unit
                        WHEN 'Day'   THEN p.price * 365
                        WHEN 'Month' THEN p.price * 12
                        WHEN 'Year'  THEN p.price * 1
                        ELSE p.price * 12
                    END
                ), 0) AS total_value,
                COALESCE(SUM(
                    CASE rc.payment_term
                        WHEN 'daily'        THEN rc.total_rent * 365
                        WHEN 'monthly'      THEN rc.total_rent * 12
                        WHEN 'quarterly'    THEN rc.total_rent * 4
                        WHEN 'half_year'    THEN rc.total_rent * 2
                        WHEN 'year'         THEN rc.total_rent * 1
                        WHEN 'full_payment' THEN rc.total_rent * 1
                        ELSE rc.total_rent * 12
                    END
                ), 0) AS annual_rent
                   FROM property_details p
                       JOIN tenancy_details rc
                   ON rc.property_id = p.id
                   WHERE p.stage = 'on_lease'
                     AND rc.contract_type = 'running_contract'
                   GROUP BY DATE_TRUNC('month', rc.start_date)
                   ORDER BY DATE_TRUNC('month', rc.start_date)
                   """)

        rows = cr.dictfetchall() or []

        # ── Sparkline — real per month yield ──
        sparkline_data = [
            round(float(r['annual_rent']) / float(r['total_value']) * 100, 1)
            if float(r.get('total_value') or 0) > 0 else 0
            for r in rows
        ]

        # ── KPI — overall yield across ALL months ──
        total_annual_rent = sum(float(r['annual_rent']) for r in rows)
        total_value = sum(float(r['total_value']) for r in rows)
        rental_yield = round(total_annual_rent / total_value * 100, 1) if total_value else 0

        # ── Fallback only when zero data ──
        if not sparkline_data:
            sparkline_data = [0] * 9

        # ── 9-point sparkline history for each KPI ────────────────────────────
        occ_spark = self._occupancy_sparkline_9()
        rev_spark = self._revenue_sparkline_9()
        contract_spark = self._contract_sparkline_9()

        return [
            {
                'l': 'Occupancy Rate', 'v': f"{occupancy_rate}%", 'tr': 0.0,
                'sub': f"{occupied} of {total_props} units",
                'ic': 'M3 11l9-8 9 8M5 10v10h14V10M10 20v-6h4v6',
                'd': occ_spark,
                'action': {'model': 'property.details', 'name': 'Occupancy Rate',
                           'domain': [('stage', 'in', ('on_lease', 'sale'))]},
            },
            {
                'l': 'Total Revenue', 'v': format_money(revenue_curr), 'tr': rev_trend,
                'sub': f"{today.strftime('%b %Y')} · All properties",
                'ic': 'M12 3v18M17 7H9.5a2.5 2.5 0 000 5h5a2.5 2.5 0 010 5H6',
                'd': rev_spark,
                'action': {'model': 'account.move', 'name': 'Total Revenue',
                           'domain': [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                                      ('invoice_date', '>=', str(first_of_month)), ('invoice_date', '<=', str(today))]},
            },
            {
                'l': 'Rental Yield', 'v': f"{rental_yield}%", 'tr': 0.0,
                'sub': 'Portfolio avg · FY',
                'ic': 'M3 17l6-6 4 4 8-8M14 7h7v7',
                'd': sparkline_data,
                'action': {'model': 'property.details', 'name': 'Rental Yield',
                           'domain': [('sale_lease', '=', 'for_tenancy')]},
            },
            {
                'l': 'Active Contracts', 'v': str(active_contracts), 'tr': 0.0,
                'sub': 'All rent contracts',
                'ic': 'M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8zM14 3v5h5',
                'd': contract_spark,
                'action': {'model': 'tenancy.details', 'name': 'Active Contracts',
                           'domain': [('contract_type', '=', 'running_contract')]},
            },
            {
                'l': 'Churn Rate', 'v': f"{churn_rate}%", 'tr': 0.0,
                'sub': f"{churned} exits · last 30 days",
                'ic': 'M3 17l6-6 4 4 8-8M14 17h7v-7',
                'd': churn_spark,
                'action': {'model': 'tenancy.details', 'name': 'Churn Rate',
                           'domain': [
                               ('contract_type', 'in', ['cancel_contract', 'close_contract', 'expire_contract']),
                               ('write_date', '>=', (today - timedelta(days=30)).isoformat())]},
            },
            {
                'l': 'Renewals Due', 'v': str(renewals_due), 'tr': 0.0,
                'sub': 'Next 60 days · action needed',
                'ic': 'M3 5h18M3 10h18M3 15h12',
                'd': [max(0, renewals_due - (8 - i) * 2) for i in range(9)],
                'action': {'model': 'tenancy.details', 'name': 'Renewals Due',
                           'domain': [('contract_type', '=', 'running_contract'),
                                      ('duration_end_date', '>=', today.isoformat()),
                                      ('duration_end_date', '<=', due_cutoff.isoformat())]},
            },
        ]

    def _occupancy_sparkline_9(self):
        """9-month occupancy rate history (one SQL query)."""
        cr = request.env.cr
        cr.execute("""
                   WITH months AS (SELECT generate_series(
                                                  date_trunc('month', NOW() - INTERVAL '8 months'),
                                                  date_trunc('month', NOW()),
                                                  '1 month'
                                          ) AS mo),
                        totals AS (SELECT COUNT(*) AS t
                                   FROM property_details)
                   SELECT TO_CHAR(m.mo, 'Mon') AS label,
                          ROUND(
                                  100.0 * COUNT(td.id) FILTER (WHERE td.start_date <= (m.mo + INTERVAL '1 month - 1 day')
                                                   AND (td.duration_end_date IS NULL OR td.duration_end_date >= m.mo)
                                                   AND td.contract_type = 'running_contract')
                    / NULLIF((SELECT t FROM totals), 0)
                              , 1)             AS occ
                   FROM months m
                            LEFT JOIN tenancy_details td ON TRUE
                   GROUP BY m.mo
                   ORDER BY m.mo
                   """)
        rows = cr.fetchall()
        return [float(r[1] or 0) for r in rows] or [0] * 9

    def _revenue_sparkline_9(self):
        """9-month revenue sparkline (in Lakhs)."""
        cr = request.env.cr
        cr.execute("""
                   SELECT TO_CHAR(date_trunc('month', invoice_date), 'Mon')          AS mo,
                          ROUND(COALESCE(SUM(amount_untaxed_signed), 0) / 100000, 1) AS rev_l
                   FROM account_move
                   WHERE move_type = 'out_invoice'
                     AND state = 'posted'
                     AND invoice_date >= NOW() - INTERVAL '9 months'
                   GROUP BY date_trunc('month', invoice_date)
                   ORDER BY date_trunc('month', invoice_date)
                   """)
        rows = cr.fetchall()
        return [float(r[1] or 0) for r in rows] or [0] * 9

    def _contract_sparkline_9(self):
        """9-month running contract count."""
        cr = request.env.cr
        cr.execute("""
                   WITH months AS (SELECT generate_series(
                                                  date_trunc('month', NOW() - INTERVAL '8 months'),
                                                  date_trunc('month', NOW()),
                                                  '1 month'
                                          ) AS mo)
                   SELECT TO_CHAR(m.mo, 'Mon') AS label,
                          COUNT(td.id)            FILTER (
                    WHERE td.contract_type = 'running_contract'
                    AND td.start_date <= (m.mo + INTERVAL '1 month - 1 day')
                    AND (td.duration_end_date IS NULL OR td.duration_end_date >= m.mo)
                ) AS cnt
                   FROM months m
                            LEFT JOIN tenancy_details td ON TRUE
                   GROUP BY m.mo
                   ORDER BY m.mo
                   """)
        rows = cr.fetchall()
        return [int(r[1] or 0) for r in rows] or [0] * 9

    # ──────────────────────────────────────────────────────────────────────────
    # SANKEY / REVENUE FLOW
    # ──────────────────────────────────────────────────────────────────────────

    def _get_sankey(self):
        """
        Revenue-flow Sankey, grounded entirely in real records.

        Sources of revenue:
          - Rent Income       → rent.invoice rows of type 'rent' / 'full_rent'
          - Deposit Income    → rent.invoice rows of type 'deposit'
          - Maintenance Income→ rent.invoice rows of type 'maintenance'
          - Sales Income      → property.vendor sold records (sale_price)

        Uses of revenue:
          - Broker Commission → tenancy_details.commission + property_vendor.broker_final_commission
          - Operating Expenses→ posted vendor bills (account_move.in_invoice)
          - Net Profit        → total_revenue − (commission + expenses)

        No derived/fabricated splits — every link is a real aggregate.
        """
        cr = request.env.cr
        today = date.today()
        fy_start = (
            today.replace(month=4, day=1)
            if today.month >= 4
            else today.replace(year=today.year - 1, month=4, day=1)
        )

        # Rent-book income, categorised by rent.invoice.type
        cr.execute("""
                   SELECT ri.type,
                          COALESCE(SUM(ri.amount), 0) AS total
                   FROM rent_invoice ri
                   WHERE ri.invoice_date >= %s
                   GROUP BY ri.type
                   """, (fy_start,))
        rent_by_type = {row[0]: float(row[1] or 0) for row in cr.fetchall()}
        rent_income = rent_by_type.get('rent', 0.0) + rent_by_type.get('full_rent', 0.0)
        deposit_income = rent_by_type.get('deposit', 0.0)
        maintenance_income = rent_by_type.get('maintenance', 0.0)
        other_rent_income = rent_by_type.get('penalty', 0.0) + rent_by_type.get('other', 0.0)

        # Sales income — realised from sold property_vendor records
        cr.execute("""
                   SELECT COALESCE(SUM(sale_price), 0) AS total
                   FROM property_vendor
                   WHERE stage = 'sold'
                     AND date >= %s
                   """, (fy_start,))
        sales_income = float((cr.fetchone() or [0])[0])

        # Broker commissions (real outflows from both sale + rent contracts)
        cr.execute(f"""
                   SELECT COALESCE(SUM({broker_sale_commission_expr()}), 0)
                   FROM property_vendor
                   WHERE is_any_broker = TRUE
                     AND date >= %s
                   """, (fy_start,))
        sale_commission = float((cr.fetchone() or [0])[0])

        cr.execute(f"""
                   SELECT COALESCE(SUM({broker_rent_commission_expr()}), 0)
                   FROM tenancy_details
                   WHERE is_any_broker = TRUE
                     AND start_date >= %s
                   """, (fy_start,))
        rent_commission = float((cr.fetchone() or [0])[0])
        broker_commission = sale_commission + rent_commission

        # Vendor bills (real operating expenses)
        cr.execute("""
                   SELECT COALESCE(SUM(amount_untaxed_signed), 0) AS expense
                   FROM account_move
                   WHERE move_type = 'in_invoice'
                     AND state = 'posted'
                     AND invoice_date >= %s
                   """, (fy_start,))
        operating_expense = abs(float((cr.fetchone() or [0])[0]))

        total_revenue = rent_income + deposit_income + maintenance_income + other_rent_income + sales_income
        total_outflow = broker_commission + operating_expense
        net_profit = max(total_revenue - total_outflow, 0.0)

        # Link builder — Sankey silently drops zero-valued links, so we
        # coerce anything < epsilon to None and skip it. No hidden minimums.
        def link(src, tgt, value):
            if value is None or value <= 0.01:
                return None
            return {'source': src, 'target': tgt, 'value': round(value, 2)}

        nodes = [
            {'name': 'Rent Income'},
            {'name': 'Deposit Income'},
            {'name': 'Maintenance Income'},
            {'name': 'Sales Income'},
            {'name': 'Total Revenue'},
            {'name': 'Broker Commission'},
            {'name': 'Operating Expenses'},
            {'name': 'Net Profit'},
        ]
        if other_rent_income > 0:
            nodes.insert(3, {'name': 'Other Rent Income'})

        raw_links = [
            link('Rent Income',         'Total Revenue', rent_income),
            link('Deposit Income',      'Total Revenue', deposit_income),
            link('Maintenance Income',  'Total Revenue', maintenance_income),
            link('Other Rent Income',   'Total Revenue', other_rent_income),
            link('Sales Income',        'Total Revenue', sales_income),
            link('Total Revenue',       'Broker Commission',  broker_commission),
            link('Total Revenue',       'Operating Expenses', operating_expense),
            link('Total Revenue',       'Net Profit',         net_profit),
        ]
        links = [l for l in raw_links if l is not None]

        # Drop orphan nodes so the chart does not render empty columns.
        referenced = {l['source'] for l in links} | {l['target'] for l in links}
        nodes = [n for n in nodes if n['name'] in referenced]

        return {
            'data': nodes,
            'links': links,
            'totals': {
                'revenue': round(total_revenue, 2),
                'commission': round(broker_commission, 2),
                'expenses': round(operating_expense, 2),
                'net_profit': round(net_profit, 2),
                'revenue_formatted':    format_money(total_revenue),
                'commission_formatted': format_money(broker_commission),
                'expenses_formatted':   format_money(operating_expense),
                'profit_formatted':     format_money(net_profit),
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # RADAR CHART
    # ──────────────────────────────────────────────────────────────────────────

    def _get_radar(self):
        """
        Portfolio health radar — 6 KPI dimensions, current vs previous period.

        Every dimension is computed from real data for BOTH periods.
        No constant-offset shortcuts (previously `prev = curr − N`).

        Dimensions: Occupancy, Yield, Collection, Maintenance Health,
                    Contracts Health, Revenue Growth.
        """
        cr = request.env.cr
        today = date.today()
        month_start = today.replace(day=1)
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        prev_month_end = month_start - timedelta(days=1)

        # Occupancy now (snapshot) vs first day of the current month
        cr.execute("""
                   SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE stage = 'on_lease')
                                   / NULLIF(COUNT(*), 0), 1)
                   FROM property_details
                   """)
        occ_curr = float((cr.fetchone() or [0])[0] or 0)

        cr.execute("""
                   SELECT ROUND(100.0 *
                                COUNT(DISTINCT td.property_id) FILTER (
                                    WHERE td.start_date <= %s
                                      AND (td.duration_end_date IS NULL
                                           OR td.duration_end_date >= %s)
                                )
                                / NULLIF((SELECT COUNT(*) FROM property_details), 0), 1)
                   FROM tenancy_details td
                   WHERE td.contract_type = 'running_contract'
                      OR td.duration_end_date >= %s
                   """, (prev_month_end, prev_month_start, prev_month_start))
        occ_prev = float((cr.fetchone() or [0])[0] or 0)

        # Collection rate — paid / invoiced, for each period
        def _collection_rate(start, end):
            cr.execute("""
                       SELECT ROUND(100.0 *
                                    COALESCE(SUM(CASE WHEN payment_state = 'paid'
                                                      THEN amount_untaxed_signed ELSE 0 END), 0)
                                    / NULLIF(SUM(amount_untaxed_signed), 0), 1)
                       FROM account_move
                       WHERE move_type = 'out_invoice'
                         AND state = 'posted'
                         AND invoice_date BETWEEN %s AND %s
                       """, (start, end))
            return float((cr.fetchone() or [0])[0] or 0)

        coll_curr = _collection_rate(month_start, today)
        coll_prev = _collection_rate(prev_month_start, prev_month_end)

        # Maintenance health — % closed tickets in the period
        def _maintenance_score(start, end):
            cr.execute("""
                       SELECT COUNT(*) FILTER (WHERE ms.done IS TRUE) AS closed,
                              COUNT(*)                                AS total
                       FROM maintenance_request mr
                            LEFT JOIN maintenance_stage ms ON mr.stage_id = ms.id
                       WHERE mr.create_date BETWEEN %s AND %s
                       """, (start, end))
            row = cr.dictfetchone() or {}
            total = row.get('total', 0) or 0
            closed = row.get('closed', 0) or 0
            return round(closed / total * 100, 1) if total else 100.0

        maint_curr = _maintenance_score(month_start, today)
        maint_prev = _maintenance_score(prev_month_start, prev_month_end)

        # Contracts health — % running contracts active during each period
        def _contracts_score(at_date):
            cr.execute("""
                       SELECT ROUND(100.0 *
                                    COUNT(*) FILTER (
                                        WHERE start_date <= %s
                                          AND (duration_end_date IS NULL
                                               OR duration_end_date >= %s)
                                          AND contract_type IN ('running_contract', 'new_contract')
                                    )
                                    / NULLIF(COUNT(*), 0), 1)
                       FROM tenancy_details
                       """, (at_date, at_date))
            return float((cr.fetchone() or [0])[0] or 0)

        cont_curr = _contracts_score(today)
        cont_prev = _contracts_score(prev_month_end)

        # Yield score — normalised 15% annual yield == 100
        def _yield_score(as_of):
            cr.execute("""
                       SELECT COALESCE(SUM(p.price) * 12, 0) AS annual_rent,
                              COALESCE(SUM(p.price), 0)      AS unit_price_sum
                       FROM property_details p
                                JOIN tenancy_details td ON td.property_id = p.id
                       WHERE td.start_date <= %s
                         AND (td.duration_end_date IS NULL OR td.duration_end_date >= %s)
                       """, (as_of, as_of))
            row = cr.fetchone() or (0, 0)
            annual, denom = float(row[0] or 0), float(row[1] or 0)
            if denom <= 0:
                return 0.0
            yield_pct = (annual / denom) * 100
            return round(min(yield_pct * (100 / 15), 100), 1)

        yield_curr = _yield_score(today)
        yield_prev = _yield_score(prev_month_end)

        # Revenue growth — % of prior period revenue, capped at 100
        cr.execute("""
                   SELECT COALESCE(SUM(
                              CASE WHEN invoice_date >= %s AND invoice_date <= %s
                                   THEN amount_untaxed_signed ELSE 0 END
                          ), 0) AS curr,
                          COALESCE(SUM(
                              CASE WHEN invoice_date >= %s AND invoice_date <= %s
                                   THEN amount_untaxed_signed ELSE 0 END
                          ), 0) AS prev,
                          COALESCE(SUM(
                              CASE WHEN invoice_date >= %s AND invoice_date < %s
                                   THEN amount_untaxed_signed ELSE 0 END
                          ), 0) AS prev_prev
                   FROM account_move
                   WHERE move_type = 'out_invoice'
                     AND state = 'posted'
                     AND invoice_date >= %s
                   """, (
            month_start, today,
            prev_month_start, prev_month_end,
            (prev_month_start - timedelta(days=31)).replace(day=1), prev_month_start,
            (prev_month_start - timedelta(days=31)).replace(day=1),
        ))
        gr_row = cr.dictfetchone() or {}
        curr_rev = abs(float(gr_row.get('curr', 0) or 0))
        prev_rev = abs(float(gr_row.get('prev', 0) or 0))
        prev_prev_rev = abs(float(gr_row.get('prev_prev', 0) or 0))

        def _growth(latest, base):
            if base <= 0:
                return 0.0 if latest <= 0 else 100.0
            return round(min(latest / base * 50, 100), 1)

        growth_curr = _growth(curr_rev, prev_rev)
        growth_prev = _growth(prev_rev, prev_prev_rev)

        return {
            'indicators': [
                {'name': 'Occupancy',      'max': 100},
                {'name': 'Yield',          'max': 100},
                {'name': 'Collection',     'max': 100},
                {'name': 'Maintenance',    'max': 100},
                {'name': 'Contracts',      'max': 100},
                {'name': 'Growth',         'max': 100},
            ],
            'current':  [occ_curr,  yield_curr,  coll_curr,  maint_curr,  cont_curr,  growth_curr],
            'previous': [occ_prev,  yield_prev,  coll_prev,  maint_prev,  cont_prev,  growth_prev],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # FORECAST CHART
    # ──────────────────────────────────────────────────────────────────────────

    def _get_forecast(self, days=90):
        """Monthly revenue forecast — historical actuals + projected."""
        cr = request.env.cr
        cr.execute("""
                   SELECT TO_CHAR(date_trunc('month', invoice_date), 'Mon YY')            AS label,
                          ROUND(COALESCE(SUM(amount_untaxed_signed), 0) / 100000, 1) AS rev
                   FROM account_move
                   WHERE move_type = 'out_invoice'
                     AND state = 'posted'
                     AND invoice_date >= NOW() - INTERVAL '12 months'
                   GROUP BY date_trunc('month', invoice_date)
                   ORDER BY date_trunc('month', invoice_date)
                   """)
        rows = cr.fetchall()
        labels = [r[0] for r in rows]
        actuals = [float(r[1] or 0) for r in rows]

        # Simple linear projection for next 3 months
        if len(actuals) >= 3:
            avg_growth = sum(
                (actuals[i] - actuals[i - 1]) for i in range(max(1, len(actuals) - 3), len(actuals))
            ) / 3
        else:
            avg_growth = 0
        last_val = actuals[-1] if actuals else 0
        from datetime import date as dt
        today = dt.today()
        for i in range(1, 4):
            future = today + relativedelta(months=i)
            labels.append(future.strftime('%b %y'))
            actuals.append(None)

        projected = [None] * len(rows) + [round(last_val + avg_growth * (i + 1), 1) for i in range(3)]
        return {'labels': labels, 'actuals': actuals, 'projected': projected}

    # ──────────────────────────────────────────────────────────────────────────
    # OCCUPANCY GAUGE
    # ──────────────────────────────────────────────────────────────────────────

    def _get_occupancy_gauge(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT COUNT(*) FILTER (WHERE stage = 'on_lease')  AS rented, COUNT(*) FILTER (WHERE stage = 'available') AS available, COUNT(*) FILTER (WHERE stage = 'booked')    AS booked, COUNT(*) FILTER (WHERE stage = 'sold')      AS sold, COUNT(*) AS total
                   FROM property_details
                   """)
        row = cr.dictfetchone() or {}
        total = row.get('total', 0) or 1
        rented = row.get('rented', 0) or 0
        occ = round(rented / total * 100, 1)
        return {
            'occupancy': occ,
            'rented': rented,
            'available': row.get('available', 0) or 0,
            'booked': row.get('booked', 0) or 0,
            'sold': row.get('sold', 0) or 0,
            'total': total,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # REVENUE MIX (bubble / donut)
    # ──────────────────────────────────────────────────────────────────────────

    def _get_revenue_mix(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT p.type                                                        AS prop_type,
                          ROUND(COALESCE(SUM(am.amount_untaxed_signed), 0) / 100000, 1) AS rev_l,
                          COUNT(am.id)                                                  AS inv_count
                   FROM account_move am
                            LEFT JOIN tenancy_details td ON td.id = am.tenancy_id
                            JOIN property_details p ON p.id = td.property_id
                   WHERE am.move_type = 'out_invoice'
                     AND am.state = 'posted'
                     AND am.invoice_date >= NOW() - INTERVAL '6 months'
                   GROUP BY p.type
                   ORDER BY rev_l DESC
                   """)
        rows = cr.fetchall()
        if not rows:
            rows = [('residential', 0, 0), ('commercial', 0, 0)]
        return [{'type': r[0], 'revenue': float(r[1] or 0), 'count': int(r[2] or 0)} for r in rows]

    # ──────────────────────────────────────────────────────────────────────────
    # TOP PROPERTIES (right panel list)
    # ──────────────────────────────────────────────────────────────────────────

    def _get_top_properties(self):
        cr = request.env.cr

        cr.execute(f"""
                   SELECT {self._lang_extract('p.name')} AS prop_name, p.type, p.stage, ROUND(COALESCE (SUM (am.amount_untaxed_signed), 0), 1) AS rev_l, {self._lang_extract('p.city')} AS city_name, p.id
                   FROM property_details p
                       LEFT JOIN tenancy_details td
                   ON td.property_id = p.id
                       LEFT JOIN account_move am ON am.tenancy_id = td.id
                       AND am.state = 'posted'
                       AND am.move_type = 'out_invoice'
                       AND am.invoice_date >= NOW() - INTERVAL '3 months'
                   GROUP BY p.id, p.name, p.type, p.stage, p.city
                   ORDER BY rev_l DESC NULLS LAST
                       LIMIT 6
                   """)
        rows = cr.fetchall()
        return [
            {
                'name': r[0] or '',
                'type': TYPE_LABELS.get(r[1], 'Residential'),
                'stage': r[2],
                'rev': format_money(float(r[3] or 0)),
                'city': r[4] or '',
                'id': r[5] or 0,
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # OVERDUE INVOICES TABLE
    # ──────────────────────────────────────────────────────────────────────────

    def _get_overdue_invoices(self):
        cr = request.env.cr
        today = date.today()
        cr.execute(f"""
                   SELECT rp.name                    AS tenant,
                          {self._lang_extract('pd.name')} AS property,
                          am.invoice_date_due        AS due,
                          am.amount_residual         AS amount,
                          (%s - am.invoice_date_due) AS days_overdue,
                          am.payment_state,
                          am.id
                   FROM account_move am
                            LEFT JOIN tenancy_details td ON td.id = am.tenancy_id
                            LEFT JOIN property_details pd ON pd.id = td.property_id
                            LEFT JOIN res_partner rp ON rp.id = am.partner_id
                   WHERE am.move_type = 'out_invoice'
                     AND am.state = 'posted'
                     AND am.payment_state NOT IN ('paid', 'in_payment')
                     AND am.invoice_date_due < %s
                   ORDER BY days_overdue DESC LIMIT 10
                   """, (today, today))
        rows = cr.fetchall()
        return [
            {
                'tenant': r[0] or 'N/A',
                'property': r[1] or 'N/A',
                'due': r[2].isoformat() if r[2] else '',
                'amount': format_money(float(r[3] or 0)),
                'days': int(r[4] if r[4] else 0),
                'status': r[5] or 'not_paid',
                'id': r[6] or 0,
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # RIGHT PANEL METRICS
    # ──────────────────────────────────────────────────────────────────────────

    def _get_right_panel(self):
        cr = request.env.cr
        today = date.today()

        # Portfolio value
        cr.execute("SELECT COALESCE(SUM(price), 0) FROM property_details")
        pv_row = cr.fetchone()
        portfolio_value = float(pv_row[0] if pv_row else 0)

        # Average lease term (months)
        cr.execute("""
                   SELECT COALESCE(AVG(
                                           EXTRACT(MONTH FROM AGE(COALESCE(duration_end_date, NOW()), start_date)) +
                                           EXTRACT(YEAR FROM AGE(COALESCE(duration_end_date, NOW()), start_date)) * 12
                                   ), 0)
                   FROM tenancy_details
                   WHERE start_date IS NOT NULL
                     AND contract_type = 'running_contract'
                   """)
        alt_row = cr.fetchone()
        avg_lease = round(float(alt_row[0] if alt_row else 0), 0)

        # Pending invoices
        cr.execute("""
                   SELECT COUNT(*) AS cnt, COALESCE(SUM(amount_residual), 0) AS total
                   FROM account_move
                   WHERE move_type = 'out_invoice'
                     AND state = 'posted'
                     AND payment_state NOT IN ('paid', 'in_payment')
                   """)
        pending_row = cr.dictfetchone() or {}
        pending_amt = float(pending_row.get('total', 0) or 0)
        pending_cnt = int(pending_row.get('cnt', 0) or 0)

        # Revenue 30 day sparkline
        cr.execute("""
                   SELECT TO_CHAR(gs::date, 'DD') AS day,
                COALESCE(SUM(am.amount_untaxed_signed), 0) AS rev
                   FROM generate_series(%s - INTERVAL '29 days', %s, INTERVAL '1 day') gs
                       LEFT JOIN account_move am
                   ON am.invoice_date = gs:: date
                       AND am.move_type = 'out_invoice' AND am.state = 'posted'
                   GROUP BY gs
                   ORDER BY gs
                   """, (today, today))
        spark_rows = cr.fetchall()
        spark_data = [round(float(r[1] or 0), 1) for r in spark_rows]

        # Real KPIs for the right-panel "Key Metrics" — percentages are
        # normalised against meaningful targets, not arbitrary constants.
        monthly_collection_target = self._estimate_collection_target()
        collection_month_to_date = sum(spark_data)

        portfolio_pct = min(
            int(collection_month_to_date / monthly_collection_target * 100)
            if monthly_collection_target else 0, 100
        )
        lease_pct = min(int(avg_lease / 24 * 100), 100) if avg_lease else 0
        pending_pct = min(
            int(pending_amt / monthly_collection_target * 100)
            if monthly_collection_target else 0, 100
        )

        return {
            'kpis': [
                {'lbl': 'Portfolio Value', 'val': format_money(portfolio_value),
                 'pct': portfolio_pct, 'd': 'Total asset value'},
                {'lbl': 'Avg Lease Term', 'val': f"{int(avg_lease)} mo",
                 'pct': lease_pct, 'd': 'Running contracts'},
                {'lbl': 'Pending Invoices', 'val': format_money(pending_amt),
                 'pct': pending_pct, 'd': f"{pending_cnt} invoices"},
            ],
            'spark_data': spark_data,
            'spark_total': format_money(collection_month_to_date),
        }

    def _estimate_collection_target(self):
        """
        Sum of annualised-to-monthly rent across running contracts — used as
        a normalising denominator for right-panel percentage gauges.
        Returns 0 if no running contracts exist.
        """
        cr = request.env.cr
        cr.execute("""
                   SELECT COALESCE(SUM(
                       CASE td.payment_term
                           WHEN 'daily'     THEN td.total_rent * 30
                           WHEN 'monthly'   THEN td.total_rent
                           WHEN 'quarterly' THEN td.total_rent / 3.0
                           WHEN 'half_year' THEN td.total_rent / 6.0
                           WHEN 'year'      THEN td.total_rent / 12.0
                           ELSE td.total_rent
                       END
                   ), 0)
                   FROM tenancy_details td
                   WHERE td.contract_type = 'running_contract'
                   """)
        row = cr.fetchone()
        return float(row[0] or 0) if row else 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # UPCOMING EVENTS
    # ──────────────────────────────────────────────────────────────────────────

    def _get_upcoming_events(self):
        cr = request.env.cr
        today = date.today()
        cutoff = today + timedelta(days=14)
        cr.execute(f"""
                   SELECT td.tenancy_seq       AS ref,
                          rp.name              AS tenant,
                          {self._lang_extract('pd.name')} AS property,
                          td.duration_end_date AS event_date,
                          'expiry'             AS event_type,
                          td.id
                   FROM tenancy_details td
                            LEFT JOIN property_details pd ON pd.id = td.property_id
                            LEFT JOIN res_partner rp ON rp.id = td.tenancy_id
                   WHERE td.contract_type = 'running_contract'
                     AND td.duration_end_date BETWEEN %s AND %s
                   ORDER BY td.duration_end_date LIMIT 8
                   """, (today, cutoff))
        rows = cr.fetchall()
        return [
            {
                'ref': r[0], 'tenant': r[1] or 'N/A', 'property': r[2] or 'N/A',
                'date': r[3].isoformat() if r[3] else '',
                'type': r[4],
                'days_left': (r[3] - today).days if r[3] else 0,
                'id': r[5]
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # ACTIVITY FEED
    # ──────────────────────────────────────────────────────────────────────────

    def _get_activity_feed(self):
        """
        Live activity — chatter logs, notes and system events from the
        last 7 days across rental-domain models.

        Fixes applied vs previous version:
          - Interval widened from 5 hours → 7 days so data actually appears
          - Removed contradictory double message_type filter
          - Empty-body messages now fall back to subtype name, then model label
            so nothing is silently dropped
          - message_type='email' excluded cleanly with a single != check
          - Removed stray print() debug statement
        """
        cr = request.env.cr

        cr.execute("""
                   SELECT mm.date,
                          mm.body,
                          mm.subject,
                          rp.name  AS author_name,
                          mm.res_id,
                          mm.model,
                          mm.message_type,
                          mst.name AS subtype_name
                   FROM mail_message mm
                            LEFT JOIN res_partner rp ON rp.id = mm.author_id
                            LEFT JOIN mail_message_subtype mst ON mst.id = mm.subtype_id
                   WHERE mm.model = ANY (%s)
                     AND mm.message_type != 'email'
              AND mm.date         >= NOW() - INTERVAL '7 days'
                   ORDER BY mm.date DESC
                       LIMIT 30
                   """, (list(ACTIVITY_MODELS),))

        rows = cr.fetchall()

        import re
        tag_re = re.compile(r'<[^>]+>')
        ws_re = re.compile(r'\s+')

        def _strip_html(raw):
            if not raw:
                return ''
            text = raw.replace('<br>', ' ').replace('<br/>', ' ').replace('</p>', ' ')
            text = tag_re.sub('', text)
            return ws_re.sub(' ', text).strip()[:120]

        feed = []
        for msg_date, body_html, subject, author_name, res_id, model, message_type, subtype_name in rows:
            subtype_str = _resolve_translated(subtype_name)

            # Build the display text — try body first, then subject,
            # then subtype name, then a generic model label so nothing
            # is ever silently dropped.
            body_text = (
                    _strip_html(body_html)
                    or (subject or '').strip()
                    or subtype_str.strip()
                    or f"Activity on {ACTIVITY_MODEL_LABELS.get(model, model)}"
            )

            feed.append({
                'ts': msg_date.isoformat() if msg_date else '',
                'body': body_text,
                'author': _resolve_translated(author_name) if isinstance(author_name, dict) else (author_name or 'System'),
                'model': model,
                'label': ACTIVITY_MODEL_LABELS.get(model, model),
                'res_id': res_id,
                'kind': ACTIVITY_KIND_BY_MESSAGE_TYPE.get(message_type, 'log'),
            })

            if len(feed) >= 8:
                break

        return feed

    # ──────────────────────────────────────────────────────────────────────────
    # MAINTENANCE STATUS (mini donut)
    # ──────────────────────────────────────────────────────────────────────────

    def _get_maintenance_status(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT ms.id        AS stage_id,
                          ms.name      AS stage_name,
                          COUNT(mr.id) AS cnt
                   FROM maintenance_request mr
                            LEFT JOIN maintenance_stage ms ON mr.stage_id = ms.id
                   GROUP BY ms.id, ms.name
                   ORDER BY ms.sequence
                   """)
        rows = cr.fetchall()
        result = []
        for r in rows:
            raw_name = r[1]
            if isinstance(raw_name, dict):
                name = raw_name.get('en_US') or next(iter(raw_name.values()), 'Unknown')
            else:
                name = raw_name or 'Unknown'
            result.append({'name': name, 'value': int(r[2] or 0)})
        return result or [
            {'name': 'Done', 'value': 0},
            {'name': 'In Progress', 'value': 0},
            {'name': 'New', 'value': 0},
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # SIDEBAR GLANCE
    # ──────────────────────────────────────────────────────────────────────────

    def _get_sidebar_glance(self):
        cr = request.env.cr
        today = date.today()
        cr.execute("""
                   SELECT COUNT(*) FILTER (WHERE stage = 'available')  AS available, COUNT(*) FILTER (WHERE stage = 'on_lease')   AS rented, COUNT(*) FILTER (WHERE stage = 'sold')       AS sold, COUNT(*) AS total
                   FROM property_details
                   """)
        row = cr.dictfetchone() or {}
        cr.execute("""
                   SELECT COUNT(*)
                   FROM tenancy_details
                   WHERE contract_type = 'running_contract'
                     AND duration_end_date BETWEEN %s AND %s
                   """, (today, today + timedelta(days=30)))
        exp_row = cr.fetchone()
        return {
            'available': row.get('available', 0),
            'rented': row.get('rented', 0),
            'sold': row.get('sold', 0),
            'total': row.get('total', 0),
            'expiring_30d': int(exp_row[0] if exp_row else 0),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # LEADS
    # ──────────────────────────────────────────────────────────────────────────

    def _get_leads(self):
        """
        Leads dashboard data.

        Returns three things the UI consumes in a single structure:
          - tiles    : total / qualified / won / conversion %
          - funnel   : New → Qualified → Won as a 3-step funnel
          - by_source: lead volume grouped by utm.source.name

        Stage buckets follow standard CRM conventions:
          - "Won" = stage marked as `is_won = TRUE` in crm_stage
          - "Qualified" = probability >= 50 (and not won/lost)
          - "New/Working" = everything else, active=TRUE
        """
        cr = request.env.cr
        env = request.env

        # Short-circuit if the crm module is not installed or the table is missing.
        cr.execute("""
                   SELECT to_regclass('public.crm_lead') IS NOT NULL,
                          to_regclass('public.crm_stage') IS NOT NULL
                   """)
        lead_exists, stage_exists = cr.fetchone()
        if not lead_exists:
            return {
                'tiles': [
                    {'k': 'Total Leads',      'v': '0', 'd': 'CRM not installed', 'cl': 'up'},
                    {'k': 'Qualified',        'v': '0', 'd': '—', 'cl': 'up'},
                    {'k': 'Converted',        'v': '0', 'd': '—', 'cl': 'up'},
                    {'k': 'Conversion Rate',  'v': '0%', 'd': '—', 'cl': 'up'},
                ],
                'funnel':   [],
                'by_source': [],
                'totals':   {'total': 0, 'qualified': 0, 'won': 0, 'conversion_rate': 0.0},
            }

        if stage_exists:
            cr.execute("""
                       SELECT COUNT(*) FILTER (WHERE l.active IS TRUE)                      AS total,
                              COUNT(*) FILTER (WHERE l.active IS TRUE
                                               AND l.probability >= 50
                                               AND COALESCE(s.is_won, FALSE) IS NOT TRUE)   AS qualified,
                              COUNT(*) FILTER (WHERE COALESCE(s.is_won, FALSE) IS TRUE)     AS won,
                              COUNT(*) FILTER (WHERE l.active IS FALSE
                                               AND COALESCE(s.is_won, FALSE) IS NOT TRUE)   AS lost,
                              COUNT(*) FILTER (WHERE l.create_date >= NOW() - INTERVAL '30 days') AS last_30
                       FROM crm_lead l
                            LEFT JOIN crm_stage s ON s.id = l.stage_id
                       """)
        else:
            # Fallback when crm.stage is absent — fall back to probability heuristics.
            cr.execute("""
                       SELECT COUNT(*) FILTER (WHERE active IS TRUE)                          AS total,
                              COUNT(*) FILTER (WHERE active IS TRUE
                                               AND probability >= 50 AND probability < 100)  AS qualified,
                              COUNT(*) FILTER (WHERE probability = 100)                      AS won,
                              COUNT(*) FILTER (WHERE active IS FALSE AND probability < 100)  AS lost,
                              COUNT(*) FILTER (WHERE create_date >= NOW() - INTERVAL '30 days') AS last_30
                       FROM crm_lead
                       """)
        row = cr.dictfetchone() or {}

        total = int(row.get('total', 0) or 0)
        qualified = int(row.get('qualified', 0) or 0)
        won = int(row.get('won', 0) or 0)
        lost = int(row.get('lost', 0) or 0)
        last_30 = int(row.get('last_30', 0) or 0)

        denom = won + lost + qualified + total
        conversion_rate = round(won / denom * 100, 1) if denom else 0.0

        # Source-wise distribution
        try:
            cr.execute("""
                       SELECT COALESCE(us.name, 'Direct / Unknown') AS source,
                              COUNT(l.id)                           AS leads,
                              COUNT(l.id) FILTER (WHERE l.probability = 100) AS converted
                       FROM crm_lead l
                            LEFT JOIN utm_source us ON us.id = l.source_id
                       WHERE l.create_date >= NOW() - INTERVAL '6 months'
                       GROUP BY us.name
                       ORDER BY leads DESC
                       LIMIT 8
                       """)
            source_rows = cr.fetchall()
        except Exception:
            source_rows = []

        by_source = [
            {'source': r[0] or 'Direct / Unknown',
             'leads':     int(r[1] or 0),
             'converted': int(r[2] or 0)}
            for r in source_rows
        ]

        # Funnel is deliberately monotonic so the chart reads top-down:
        # everyone starts as "New", a subset becomes "Qualified", a subset
        # of those is "Won". We pass RAW counts so the funnel depicts
        # absolute drop-off, not relative percentages.
        funnel = [
            {'stage': 'New',       'value': total},
            {'stage': 'Qualified', 'value': qualified},   # qualified includes downstream
            {'stage': 'Won',       'value': won},
        ]

        tiles = [
            {'k': 'Total Leads',     'v': str(total),     'd': f'{last_30} in last 30d', 'cl': 'up'},
            {'k': 'Qualified',       'v': str(qualified), 'd': 'In-flight',               'cl': 'up'},
            {'k': 'Converted (Won)', 'v': str(won),       'd': 'Closed-won',              'cl': 'up'},
            {'k': 'Conversion Rate', 'v': f'{conversion_rate}%',
             'd': f'{won}/{denom or 1} resolved', 'cl': 'up' if conversion_rate >= 20 else 'a'},
        ]

        return {
            'tiles':     tiles,
            'funnel':    funnel,
            'by_source': by_source,
            'totals':    {
                'total': total,
                'qualified': qualified,
                'won': won,
                'lost': lost,
                'conversion_rate': conversion_rate,
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PROPERTIES PAGE
    # ──────────────────────────────────────────────────────────────────────────

    def _get_property_stat_bar(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT COUNT(*) AS total,
                          COUNT(*)    FILTER (WHERE stage = 'on_lease')   AS rented, ROUND(100.0 * COUNT(*) FILTER (WHERE stage = 'on_lease') / NULLIF(COUNT(*), 0), 1) AS occ,
                          COUNT(*)    FILTER (WHERE stage = 'available')  AS vacant
                   FROM property_details
                   """)
        row = cr.dictfetchone() or {}
        return [
            {
                'v': str(row.get('total', 0)), 'k': 'Total Properties', 'd': 'Active', 'cl': 'up',
                'action': {'model': 'property.details', 'name': 'Total Properties', 'domain': []},
            },
            {
                'v': f"{row.get('occ', 0)}%", 'k': 'Occupancy', 'd': 'Current', 'cl': 'up',
                'action': {'model': 'property.details', 'name': 'Occupied Property', 'domain': [('stage', '=', 'on_lease')]},
            },
            {
                'v': str(row.get('vacant', 0)), 'k': 'Vacant Units', 'd': 'Available', 'cl': 'dn',
                'action': {'model': 'property.details', 'name': 'Occupancy Rate', 'domain': [('stage', '=', 'available')]},
            },
        ]

    def _get_occupancy_by_type(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT type,
                          COUNT(*) FILTER (WHERE stage = 'on_lease') AS occupied, COUNT(*) AS total
                   FROM property_details
                   GROUP BY type
                   ORDER BY total DESC
                   """)
        rows = cr.fetchall()
        return [{'type': TYPE_LABELS.get(r[0]), 'occupied': int(r[1] or 0), 'total': int(r[2] or 0)} for r in rows]

    def _get_portfolio_mix(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT type, COUNT(*) AS cnt
                   FROM property_details
                   GROUP BY type
                   """)
        rows = cr.fetchall()
        return [{'type': TYPE_LABELS.get(r[0]) or 'other', 'count': int(r[1] or 0)} for r in rows]

    def _get_recent_properties(self):
        """
        Properties created in the last 3 days.

        Replaces the old full grid so the dashboard stays focused on
        what's NEW — listings still in flight, newly onboarded stock.
        Full browsing happens inside Odoo via the card's quick-link.
        """
        cr = request.env.cr
        cr.execute(f"""
                   SELECT p.id,
                          {self._lang_extract('p.name')} AS name,
                          p.type,
                          p.stage,
                          p.sale_lease,
                          p.price                  AS amount,
                          {self._lang_extract('p.city')} AS city_name,
                          p.create_date
                   FROM property_details p
                   WHERE p.create_date >= NOW() - INTERVAL '3 days'
                   ORDER BY p.create_date DESC
                   LIMIT 24
                   """)
        rows = cr.fetchall()
        return [
            {
                'id':         r[0],
                'name':       r[1] or 'Untitled',
                'type':       TYPE_LABELS.get(r[2]) or 'Other',
                'stage':      r[3],
                'sale_lease': r[4],
                'amount':     float(r[5] or 0),
                'amount_formatted': format_money(float(r[5] or 0)),
                'city':       r[6] or '',
                'created':    r[7].isoformat() if r[7] else '',
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # RENT PAGE
    # ──────────────────────────────────────────────────────────────────────────

    def _get_rent_stat_bar(self):
        """Legacy rent-only stat bar — retained for older endpoints."""
        cr = request.env.cr
        today = date.today()
        cr.execute("""
                   SELECT COALESCE(SUM(amount_untaxed_signed), 0) AS this_month_rev
                   FROM account_move am
                            LEFT JOIN tenancy_details td ON td.id = am.tenancy_id
                   WHERE am.move_type = 'out_invoice'
                     AND am.state = 'posted'
                     AND am.invoice_date >= %s
                   """, (today.replace(day=1),))
        rev = float((cr.fetchone() or [0])[0] or 0)
        cr.execute("""
                   SELECT COUNT(*)
                   FROM tenancy_details
                   WHERE contract_type = 'running_contract'
                   """)
        active_cnt = int((cr.fetchone() or [0])[0])
        return [
            {'v': str(active_cnt), 'k': 'Active Contracts', 'd': 'Running', 'cl': 'up'},
            {'v': format_money(rev), 'k': 'Revenue / Month',
             'd': 'This month', 'cl': 'up'},
        ]

    def _get_rental_contracts_stat_bar(self):
        """
        Unified stat bar for the "Rental & Contracts" page.
        Combines rent KPIs (collection, running contracts) with contract
        lifecycle KPIs (expiring, overdue) — no duplication.
        """
        cr = request.env.cr
        today = date.today()
        month_start = today.replace(day=1)
        exp_cutoff = today + timedelta(days=30)

        cr.execute("""
                   SELECT COUNT(*)                                                    AS total,
                          COUNT(*) FILTER (WHERE contract_type = 'running_contract')  AS running,
                          COUNT(*) FILTER (WHERE duration_end_date BETWEEN %s AND %s) AS expiring,
                          COUNT(*) FILTER (WHERE duration_end_date < %s
                                           AND contract_type = 'running_contract')    AS overdue
                   FROM tenancy_details
                   """, (today, exp_cutoff, today))
        contract_row = cr.dictfetchone() or {}

        cr.execute("""
                   SELECT COALESCE(SUM(amount_untaxed_signed), 0)
                   FROM account_move am
                            LEFT JOIN tenancy_details td ON td.id = am.tenancy_id
                   WHERE am.move_type = 'out_invoice'
                     AND am.state = 'posted'
                     AND am.invoice_date >= %s
                   """, (month_start,))
        month_revenue = float((cr.fetchone() or [0])[0] or 0)

        return [
            {'v': str(contract_row.get('running', 0) or 0),
             'k': 'Active Contracts', 'd': 'Running', 'cl': 'up',
             'action': {'model': 'tenancy.details', 'name': 'Active Contracts',
                        'domain': [('contract_type', '=', 'running_contract')]}},
            {'v': format_money(month_revenue),
             'k': 'Revenue / Month', 'd': 'This month', 'cl': 'up',
             'action': {'model': 'account.move', 'name': 'Monthly Revenue',
                        'domain': [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                                   ('invoice_date', '>=', str(month_start))]}},
            {'v': str(contract_row.get('expiring', 0) or 0),
             'k': 'Expiring (30d)', 'd': 'Action needed', 'cl': 'a',
             'action': {'model': 'tenancy.details', 'name': 'Expiring Contracts',
                        'domain': [('duration_end_date', '>=', str(today)),
                                   ('duration_end_date', '<=', str(exp_cutoff))]}},
            {'v': str(contract_row.get('overdue', 0) or 0),
             'k': 'Overdue', 'd': 'Past end date', 'cl': 'dn',
             'action': {'model': 'tenancy.details', 'name': 'Overdue Contracts',
                        'domain': [('contract_type', '=', 'running_contract'),
                                   ('duration_end_date', '<', str(today))]}},
            {'v': str(contract_row.get('total', 0) or 0),
             'k': 'Total Contracts', 'd': 'All time', 'cl': 'up',
             'action': {'model': 'tenancy.details', 'name': 'All Contracts', 'domain': []}},
        ]

    def _get_monthly_rent_collection(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT TO_CHAR(date_trunc('month', invoice_date), 'Mon YY')                                                         AS mo,
                          ROUND(SUM(amount_untaxed_signed) FILTER (WHERE payment_state = 'paid') / 100000, 1)                     AS collected,
                          ROUND(SUM(amount_untaxed_signed) FILTER (WHERE payment_state NOT IN ('paid','in_payment')) / 100000, 1) AS outstanding
                   FROM account_move
                   WHERE move_type = 'out_invoice'
                     AND state = 'posted'
                     AND invoice_date >= NOW() - INTERVAL '12 months'
                   GROUP BY date_trunc('month', invoice_date)
                   ORDER BY date_trunc('month', invoice_date)
                   """)
        rows = cr.fetchall()
        return {
            'labels': [r[0] for r in rows],
            'collected': [float(r[1] or 0) for r in rows],
            'outstanding': [float(r[2] or 0) for r in rows],
        }

    def _get_collection_by_type(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT COALESCE(p.type, 'other')                                AS prop_type,
                          ROUND(100.0 *
                                SUM(CASE WHEN am.payment_state = 'paid' THEN am.amount_untaxed_signed ELSE 0 END)
                                    / NULLIF(SUM(am.amount_untaxed_signed), 0), 1) AS rate
                   FROM account_move am
                            LEFT JOIN tenancy_details td ON td.id = am.tenancy_id
                            JOIN property_details p ON p.id = td.property_id
                   WHERE am.move_type = 'out_invoice'
                     AND am.state = 'posted'
                     AND am.invoice_date >= NOW() - INTERVAL '3 months'
                     AND td.contract_type = 'running_contract'
                   GROUP BY COALESCE (p.type, 'other')
                   """)
        rows = cr.fetchall()
        return [{'type': TYPE_LABELS.get(r[0], 'Other'), 'rate': float(r[1] or 0)} for r in rows]

    def _get_rent_table(self):
        cr = request.env.cr
        today = date.today()
        cr.execute(f"""
                   SELECT rp.name          AS tenant,
                          {self._lang_extract('pd.name')} AS property,
                          td.total_rent    AS current_rent,
                          td.duration_end_date,
                          td.contract_type AS status,
                          td.id,
                          td.tenancy_seq
                   FROM tenancy_details td
                            LEFT JOIN property_details pd ON pd.id = td.property_id
                            LEFT JOIN res_partner rp ON rp.id = td.tenancy_id
                   WHERE td.contract_type = 'running_contract'
                   ORDER BY td.duration_end_date NULLS LAST LIMIT 20
                   """)
        rows = cr.fetchall()
        return [
            {
                'tenant': r[0] or 'N/A', 'property': r[1] or 'N/A',
                'rent': format_money(float(r[2] or 0)),
                'expiry': r[3].isoformat() if r[3] else '',
                'days_left': (r[3] - today).days if r[3] else 0,
                'status': r[4] or 'running_contract',
                'id': r[5] or 0,
                'seq': r[6] or 'N/A',
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # SALES PAGE
    # ──────────────────────────────────────────────────────────────────────────

    def _get_sales_stat_bar(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT COUNT(*) AS total,
                          COUNT(*)    FILTER (WHERE stage = 'sold') AS sold, COALESCE(SUM(sale_price) FILTER(WHERE stage = 'sold'), 0) AS revenue
                   FROM property_vendor
                   """)
        row = cr.dictfetchone() or {}
        rev = float(row.get('revenue', 0) or 0)
        return [
            {'v': str(row.get('total', 0)), 'k': 'Total Sales Contracts', 'd': 'All stages', 'cl': 'up',
             'action': {'model': 'property.vendor', 'name': 'All Sale Contracts', 'domain': []}},
            {'v': str(row.get('sold', 0)), 'k': 'Properties Sold', 'd': 'Completed', 'cl': 'up',
             'action': {'model': 'property.vendor', 'name': 'Properties Sold', 'domain': [('stage', '=', 'sold')]}},
            {'v': format_money(rev), 'k': 'Sales Revenue', 'd': 'Total', 'cl': 'up',
             'action': {'model': 'property.vendor', 'name': 'Sales Revenue', 'domain': [('stage', '=', 'sold')]}},
        ]

    def _get_sales_funnel(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT stage, COUNT(*) AS cnt
                   FROM property_vendor
                   GROUP BY stage
                   ORDER BY COUNT(*) DESC
                   """)
        rows = cr.fetchall()
        stage_labels = {'booked': 'Booked', 'sold': 'Sold', 'refund': 'Refund', 'cancel': 'Cancelled',
                        'locked': 'Locked'}
        return [{'stage': stage_labels.get(r[0], r[0] or 'Other'), 'count': int(r[1] or 0)} for r in rows]

    def _get_sales_by_type(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT COALESCE(pd.type, 'other') AS prop_type,
                          COUNT(pv.id)               AS cnt
                   FROM property_vendor pv
                            LEFT JOIN property_details pd ON pd.id = pv.property_id
                   GROUP BY COALESCE(pd.type, 'other')
                   """)
        rows = cr.fetchall()
        return [{'type': TYPE_LABELS.get(r[0], 'Other'), 'count': int(r[1] or 0)} for r in rows]

    def _get_sales_table(self):
        cr = request.env.cr
        cr.execute(f"""
                   SELECT {self._lang_extract('pd.name')} AS property,
                          pd.type  AS prop_type,
                          pd.price AS price,
                          pv.stage,
                          rp2.name AS agent,
                          pv.id AS sale_id,
                          pv.sold_seq
                   FROM property_vendor pv
                            LEFT JOIN property_details pd ON pd.id = pv.property_id
                            LEFT JOIN res_partner rp2 ON rp2.id = pv.broker_id
                   ORDER BY pv.date DESC LIMIT 20
                   """)
        rows = cr.fetchall()
        return [
            {
                'property': r[0] or 'N/A', 'type': TYPE_LABELS.get(r[1], 'Residential'),
                'price': format_money(float(r[2] or 0)), 'stage': r[3] or 'booked',
                'agent': r[4] or 'N/A',
                'id': r[5] or 0,
                'sold_seq': r[6] or 'N/A',
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # MAINTENANCE PAGE
    # ──────────────────────────────────────────────────────────────────────────

    def _get_maintenance_stat_bar(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT COUNT(mr.id) AS total,

                          COUNT(mr.id)    FILTER (
                    WHERE COALESCE(ms.done, FALSE) = FALSE
                ) AS open_cnt, COUNT(mr.id) FILTER (
                    WHERE ms.done IS TRUE
                ) AS done_cnt, COUNT(mr.id) FILTER (
                    WHERE mr.maintenance_type = 'corrective'
                ) AS corrective

                   FROM maintenance_request mr
                            LEFT JOIN maintenance_stage ms ON mr.stage_id = ms.id
                   """)
        row = cr.dictfetchone() or {}
        return [
            {'v': str(row.get('total', 0)), 'k': 'Total Requests', 'd': 'All time', 'cl': 'up',
             'action': {'model': 'maintenance.request', 'name': 'All Maintenance Requests', 'domain': []}},
            {'v': str(row.get('open_cnt', 0)), 'k': 'Open Tickets', 'd': 'Active', 'cl': 'dn',
             'action': {'model': 'maintenance.request', 'name': 'Open Tickets',
                        'domain': [('stage_id.done', '=', False)]}},
            {'v': str(row.get('done_cnt', 0)), 'k': 'Resolved', 'd': 'Completed', 'cl': 'up',
             'action': {'model': 'maintenance.request', 'name': 'Resolved Tickets',
                        'domain': [('stage_id.done', '=', True)]}},
        ]

    def _get_ticket_trends(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT TO_CHAR(date_trunc('month', mr.create_date), 'Mon YY') AS mo,

                          COUNT(mr.id)                                              FILTER (
                    WHERE COALESCE(ms.done, FALSE) = FALSE
                ) AS open_cnt, COUNT(mr.id) FILTER (
                    WHERE ms.done IS TRUE
                ) AS resolved, COUNT(mr.id) FILTER (
                    WHERE mr.priority = '3'
                ) AS escalated

                   FROM maintenance_request mr
                            LEFT JOIN maintenance_stage ms ON mr.stage_id = ms.id

                   WHERE mr.create_date >= NOW() - INTERVAL '12 months'

                   GROUP BY date_trunc('month', mr.create_date)
                   ORDER BY date_trunc('month', mr.create_date)
                   """)
        rows = cr.fetchall()
        return {
            'labels': [r[0] for r in rows],
            'open': [int(r[1] or 0) for r in rows],
            'resolved': [int(r[2] or 0) for r in rows],
            'escalated': [int(r[3] or 0) for r in rows],
        }

    def _get_maintenance_by_category(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT COALESCE(maintenance_type, 'other') AS cat,
                          COUNT(*)                            AS cnt
                   FROM maintenance_request
                   GROUP BY maintenance_type
                   ORDER BY cnt DESC
                   """)
        rows = cr.fetchall()
        return [{'cat': MAINTENANCE_TYPE.get(r[0], 'Other'), 'count': int(r[1] or 0)} for r in rows]

    def _get_maintenance_table(self):
        cr = request.env.cr
        cr.execute(f"""
                   SELECT mr.name             AS req_name,
                          {self._lang_extract('pd.name')} AS property,
                          mr.maintenance_type AS category,
                          mr.priority,
                          rp.name             AS assigned,
                          {self._lang_extract('ms.name')} AS stage,
                          mr.id

                   FROM maintenance_request mr

                            LEFT JOIN maintenance_stage ms ON mr.stage_id = ms.id
                            LEFT JOIN property_details pd ON pd.id = mr.property_id
                            LEFT JOIN res_users ru ON ru.id = mr.user_id
                            LEFT JOIN res_partner rp ON rp.id = ru.partner_id

                   ORDER BY mr.create_date DESC LIMIT 20
                   """)
        rows = cr.fetchall()
        return [
            {
                'name': r[0] or 'N/A', 'property': r[1] or 'N/A',
                'category': MAINTENANCE_TYPE.get(r[2]) or 'Corrective', 'priority': r[3] or '0',
                'assigned': r[4] or 'Unassigned', 'stage': r[5] or 'new', 'id': r[6] or 0
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # CONTRACTS PAGE
    # ──────────────────────────────────────────────────────────────────────────

    def _get_contracts_stat_bar(self):
        cr = request.env.cr
        today = date.today()
        cr.execute("""
                   SELECT COUNT(*) AS total,
                          COUNT(*)    FILTER (WHERE contract_type = 'running_contract') AS running, COUNT(*) FILTER (WHERE duration_end_date BETWEEN %s AND %s) AS expiring, COUNT(*) FILTER (WHERE duration_end_date < %s AND contract_type = 'running_contract') AS overdue
                   FROM tenancy_details
                   """, (today, today + timedelta(days=30), today))
        row = cr.dictfetchone() or {}
        exp_cutoff = today + timedelta(days=30)
        return [
            {'v': str(row.get('total', 0)), 'k': 'Total Contracts', 'd': 'All time', 'cl': 'up',
             'action': {'model': 'tenancy.details', 'name': 'All Contracts', 'domain': []}},
            {'v': str(row.get('running', 0)), 'k': 'Running', 'd': 'Active', 'cl': 'up',
             'action': {'model': 'tenancy.details', 'name': 'Running Contracts',
                        'domain': [('contract_type', '=', 'running_contract')]}},
            {'v': str(row.get('expiring', 0)), 'k': 'Expiring (30d)', 'd': 'Action needed', 'cl': 'a',
             'action': {'model': 'tenancy.details', 'name': 'Expiring Contracts',
                        'domain': [('duration_end_date', '>=', str(today)),
                                   ('duration_end_date', '<=', str(exp_cutoff))]}},
            {'v': str(row.get('overdue', 0)), 'k': 'Overdue', 'd': 'Past end date', 'cl': 'dn',
             'action': {'model': 'tenancy.details', 'name': 'Overdue Contracts',
                        'domain': [('contract_type', '=', 'running_contract'),
                                   ('duration_end_date', '<', str(today))]}},
        ]

    def _get_contracts_gantt(self):
        """Return contract timeline data for Gantt chart (first 30 contracts)."""
        cr = request.env.cr
        today = date.today()
        cr.execute("""
                   SELECT td.tenancy_seq AS seq,
                          rp.name        AS tenant,
                          td.start_date,
                          td.duration_end_date,
                          td.contract_type,
                          pd.name        AS property
                   FROM tenancy_details td
                            LEFT JOIN res_partner rp ON rp.id = td.tenancy_id
                            LEFT JOIN property_details pd ON pd.id = td.property_id
                   WHERE td.start_date IS NOT NULL
                     AND td.contract_type IN ('running_contract', 'new_contract')
                   ORDER BY td.start_date DESC LIMIT 30
                   """)
        rows = cr.fetchall()
        result = []
        for r in rows:
            start = r[2]
            end = r[3] or (start + timedelta(days=365)) if start else None
            if not start:
                continue
            days_left = (end - today).days if end else 0
            status = 'active'
            if end and end < today:
                status = 'overdue'
            elif end and days_left <= 30:
                status = 'expiring'
            result.append({
                'seq': r[0], 'tenant': r[1] or 'N/A',
                'start': start.isoformat(), 'end': end.isoformat() if end else '',
                'status': status, 'property': r[5] or 'N/A',
                'days_left': days_left,
            })
        return result

    def _get_contract_list(self):
        cr = request.env.cr
        cr.execute(f"""
                   SELECT td.tenancy_seq,
                          rp.name AS tenant,
                          {self._lang_extract('pd.name')} AS property,
                          td.total_rent,
                          td.start_date,
                          td.duration_end_date,
                          td.contract_type,
                          td.id
                   FROM tenancy_details td
                            LEFT JOIN res_partner rp ON rp.id = td.tenancy_id
                            LEFT JOIN property_details pd ON pd.id = td.property_id
                   ORDER BY td.write_date DESC LIMIT 20
                   """)
        rows = cr.fetchall()
        return [
            {
                'seq': r[0], 'tenant': r[1] or 'N/A', 'property': r[2] or 'N/A',
                'rent': format_money(float(r[3] or 0)),
                'start': r[4].isoformat() if r[4] else '',
                'end': r[5].isoformat() if r[5] else '',
                'status': r[6] or 'new_contract',
                'id': r[7] or 0
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # BROKERS PAGE
    # ──────────────────────────────────────────────────────────────────────────

    # ------------------------------------------------------------------
    # Commission is earned on BOTH sides of the business:
    #   - Sale side : property_vendor.broker_final_commission
    #   - Rent side : tenancy_details.commission
    # Every broker-facing endpoint below aggregates both sources so that
    # tiles and charts reflect the true total broker book.
    # ------------------------------------------------------------------

    def _get_brokers_stat_bar(self):
        """Broker stat bar — combined sale + rent commissions and broker count."""
        cr = request.env.cr
        cr.execute(f"""
            WITH sale_side AS (
                SELECT broker_id,
                       COALESCE(SUM({broker_sale_commission_expr('pv')}), 0) AS commission
                FROM property_vendor pv
                WHERE pv.is_any_broker = TRUE
                  AND pv.broker_id IS NOT NULL
                GROUP BY pv.broker_id
            ),
            rent_side AS (
                SELECT broker_id,
                       COALESCE(SUM({broker_rent_commission_expr('td')}), 0) AS commission
                FROM tenancy_details td
                WHERE td.is_any_broker = TRUE
                  AND td.broker_id IS NOT NULL
                GROUP BY td.broker_id
            )
            SELECT COUNT(DISTINCT broker_id)        AS broker_count,
                   COALESCE(SUM(commission), 0)     AS total_commission
            FROM (
                SELECT broker_id, commission FROM sale_side
                UNION ALL
                SELECT broker_id, commission FROM rent_side
            ) combined
        """)
        row = cr.dictfetchone() or {}
        broker_count = int(row.get('broker_count', 0) or 0)
        total_commission = float(row.get('total_commission', 0) or 0)
        return [
            {'v': str(broker_count),
             'k': 'Active Brokers', 'd': 'Sale + Rent', 'cl': 'up',
             'action': {'model': 'res.partner', 'name': 'Active Brokers',
                        'domain': [('user_type', '=', 'broker')]}},
            {'v': format_money(total_commission),
             'k': 'Total Commission', 'd': 'Sale + Rent · All time', 'cl': 'up',
             'action': {'model': 'property.vendor', 'name': 'Commission — Sale Contracts',
                        'domain': [('is_any_broker', '=', True)]}},
        ]

    def _get_broker_performance(self):
        """Per-broker deal count + commission, summing sale and rent books."""
        cr = request.env.cr
        cr.execute(f"""
                   WITH per_broker AS (
                       SELECT pv.broker_id,
                              COUNT(pv.id)                              AS deals,
                              COALESCE(SUM({broker_sale_commission_expr('pv')}), 0) AS commission,
                              0                                         AS rent_deals
                       FROM property_vendor pv
                       WHERE pv.is_any_broker = TRUE AND pv.broker_id IS NOT NULL
                       GROUP BY pv.broker_id
                       UNION ALL
                       SELECT td.broker_id,
                              0                                         AS deals,
                              COALESCE(SUM({broker_rent_commission_expr()}), 0)           AS commission,
                              COUNT(td.id)                              AS rent_deals
                       FROM tenancy_details td
                       WHERE td.is_any_broker = TRUE AND td.broker_id IS NOT NULL
                       GROUP BY td.broker_id
                   )
                   SELECT rp.name,
                          SUM(pb.deals + pb.rent_deals)  AS total_deals,
                          SUM(pb.commission)             AS total_commission
                   FROM per_broker pb
                            LEFT JOIN res_partner rp ON rp.id = pb.broker_id
                   GROUP BY rp.name
                   ORDER BY total_deals DESC
                   LIMIT 10
                   """)
        rows = cr.fetchall()
        return [
            {
                'broker': r[0] or 'N/A',
                'deals': int(r[1] or 0),
                'commission': float(r[2] or 0),
            }
            for r in rows
        ]

    def _get_commission_breakdown(self):
        """
        Commission breakdown grouped by source (Sale vs Rent) and by
        commission_type (Fixed vs Percentage) within each. The chart
        can now meaningfully show "where commissions are earned".
        """
        cr = request.env.cr
        cr.execute(f"""
                   SELECT 'Sale'                           AS source,
                          CASE commission_type
                              WHEN 'f' THEN 'Fixed'
                              WHEN 'p' THEN 'Percentage'
                              ELSE 'Other'
                          END                              AS commission_mode,
                          COUNT(*)                         AS contract_count,
                          COALESCE(SUM({broker_sale_commission_expr()}), 0) AS total_commission
                   FROM property_vendor
                   WHERE is_any_broker = TRUE
                   GROUP BY commission_type
                   UNION ALL
                   SELECT 'Rent'                           AS source,
                          CASE commission_type
                              WHEN 'f' THEN 'Fixed'
                              WHEN 'p' THEN 'Percentage'
                              ELSE 'Other'
                          END                              AS commission_mode,
                          COUNT(*)                         AS contract_count,
                          COALESCE(SUM({broker_rent_commission_expr()}), 0)     AS total_commission
                   FROM tenancy_details
                   WHERE is_any_broker = TRUE
                   GROUP BY commission_type
                   """)
        rows = cr.fetchall()
        breakdown = [
            {
                'source': r[0],
                'type': r[1],
                'count': int(r[2] or 0),
                'total': float(r[3] or 0),
            }
            for r in rows
            if float(r[3] or 0) > 0 or int(r[2] or 0) > 0
        ]

        sale_total = sum(b['total'] for b in breakdown if b['source'] == 'Sale')
        rent_total = sum(b['total'] for b in breakdown if b['source'] == 'Rent')

        return {
            'breakdown': breakdown,
            'by_source': [
                {'name': 'Sale Commission',   'value': round(sale_total, 2)},
                {'name': 'Rental Commission', 'value': round(rent_total, 2)},
            ],
            'totals': {
                'sale':  sale_total,
                'rent':  rent_total,
                'total': sale_total + rent_total,
                'sale_formatted':  format_money(sale_total),
                'rent_formatted':  format_money(rent_total),
                'total_formatted': format_money(sale_total + rent_total),
            },
        }

    def _get_broker_table(self):
        """Broker directory table — combined sale + rent performance."""
        cr = request.env.cr
        cr.execute(f"""
                   WITH per_broker AS (
                       SELECT pv.broker_id,
                              COUNT(pv.id)                              AS deals,
                              COALESCE(SUM({broker_sale_commission_expr('pv')}), 0) AS commission,
                              MAX(pv.date)                              AS last_deal
                       FROM property_vendor pv
                       WHERE pv.is_any_broker = TRUE AND pv.broker_id IS NOT NULL
                       GROUP BY pv.broker_id
                       UNION ALL
                       SELECT td.broker_id,
                              COUNT(td.id)                              AS deals,
                              COALESCE(SUM({broker_rent_commission_expr()}), 0)           AS commission,
                              MAX(td.start_date)                        AS last_deal
                       FROM tenancy_details td
                       WHERE td.is_any_broker = TRUE AND td.broker_id IS NOT NULL
                       GROUP BY td.broker_id
                   )
                   SELECT rp.id,
                          rp.name,
                          rp.phone,
                          SUM(pb.deals)                      AS total_deals,
                          SUM(pb.commission)                 AS total_commission,
                          MAX(pb.last_deal)                  AS last_deal
                   FROM per_broker pb
                            LEFT JOIN res_partner rp ON rp.id = pb.broker_id
                   GROUP BY rp.id, rp.name, rp.phone
                   ORDER BY total_deals DESC
                   LIMIT 20
                   """)
        rows = cr.fetchall()
        return [
            {
                'id':         r[0] or 0,
                'broker':     r[1] or 'N/A',
                'phone':      r[2] or '',
                'deals':      int(r[3] or 0),
                'commission': format_money(float(r[4] or 0)),
                'last_deal':  r[5].isoformat() if r[5] else '',
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # MAP PAGE
    # ──────────────────────────────────────────────────────────────────────────

    def _get_map_properties(self):
        cr = request.env.cr
        cr.execute(f"""
                   SELECT p.id,
                          {self._lang_extract('p.name')},
                          p.type,
                          p.stage,
                          p.latitude,
                          p.longitude,
                          p.price,
                          p.price,
                          {self._lang_extract('p.city')} AS city_name, p.total_area
                   FROM property_details p
                   WHERE p.latitude IS NOT NULL
                     AND p.latitude != ''
                     AND p.longitude IS NOT NULL
                     AND p.longitude != ''
                   """)
        rows = cr.fetchall()
        result = []
        for r in rows:
            try:
                lat = float(r[4]) if r[4] else None
                lng = float(r[5]) if r[5] else None
                if lat is None or lng is None:
                    continue
                result.append({
                    'id': r[0], 'name': r[1], 'type': TYPE_LABELS.get(r[2], 'Residential'),
                    'stage': r[3], 'lat': lat, 'lng': lng,
                    'rent': float(r[6] or 0), 'price': float(r[7] or 0),
                    'city': r[8] or '', 'area': float(r[9] or 0),
                })
            except (ValueError, TypeError):
                continue
        return result

    def _get_regional_data(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT COALESCE(pr.name, 'Unassigned') AS region,
                          COUNT(pd.id)                    AS total,
                          COUNT(pd.id)                       FILTER (WHERE pd.stage = 'on_lease') AS rented
                   FROM property_details pd
                            LEFT JOIN property_region pr ON pr.id = pd.region_id
                   GROUP BY pr.name
                   ORDER BY total DESC LIMIT 10
                   """)
        rows = cr.fetchall()
        return [{'region': r[0], 'total': int(r[1] or 0), 'rented': int(r[2] or 0)} for r in rows]

    def _get_city_distribution(self):
        cr = request.env.cr
        cr.execute(f"""
                   SELECT COALESCE({self._lang_extract('rc.name')}, 'Unknown') AS city,
                          COUNT(*)                                AS cnt
                   FROM property_details p
                            LEFT JOIN property_res_city rc ON rc.id = p.city_id
                   GROUP BY rc.id, rc.name
                   ORDER BY cnt DESC LIMIT 8
                   """)
        rows = cr.fetchall()
        return [{'city': r[0], 'count': int(r[1] or 0)} for r in rows]

    def _get_density_data(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT type, COUNT(*) AS cnt
                   FROM property_details
                   GROUP BY type
                   """)
        rows = cr.fetchall()
        return [{'type': r[0] or 'other', 'count': int(r[1] or 0)} for r in rows]

    def _get_city_trend(self):
        cr = request.env.cr
        cr.execute("""
                   SELECT TO_CHAR(date_trunc('month', create_date), 'Mon YY') AS mo,
                          COUNT(*)                                            AS new_props
                   FROM property_details
                   WHERE create_date >= NOW() - INTERVAL '12 months'
                   GROUP BY date_trunc('month', create_date)
                   ORDER BY date_trunc('month', create_date)
                   """)
        rows = cr.fetchall()
        return {'labels': [r[0] for r in rows], 'data': [int(r[1] or 0) for r in rows]}
