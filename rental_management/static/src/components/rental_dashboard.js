/** @odoo-module **/
/**
 * Rental Management — Dynamic Dashboard
 * Fetches all data from /rental/dashboard/* endpoints and renders
 * the Estala-style dashboard with ApexCharts + ECharts.
 */

import {Component, useState, onMounted, onWillUnmount, useRef} from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

// ─────────────────────────────────────────────────────────────────────────────
//  THEME PALETTES — 10 predefined professional colour themes
// ─────────────────────────────────────────────────────────────────────────────
const THEMES = {
    Teal: {
        c1: "#0D9488",
        c2: "#5EEAD4",
        bg: "#F0FDFB",
        bg2: "#CCFBF1",
        text: "#042F2E",
        soft: "#5B8A84",
        grad: "linear-gradient(135deg,#065F5A,#0D9488,#5EEAD4)"
    },
    Amber: {
        c1: "#D97706",
        c2: "#FCD34D",
        bg: "#FFFBEB",
        bg2: "#FEF3C7",
        text: "#1C0A00",
        soft: "#92724A",
        grad: "linear-gradient(135deg,#B45309,#D97706,#FCD34D)"
    },
    Indigo: {
        c1: "#4F46E5",
        c2: "#A5B4FC",
        bg: "#F5F3FF",
        bg2: "#EDE9FE",
        text: "#1E1B4B",
        soft: "#6366A0",
        grad: "linear-gradient(135deg,#3730A3,#4F46E5,#A5B4FC)"
    },
    Rose: {
        c1: "#E11D48",
        c2: "#FDA4AF",
        bg: "#FFF1F2",
        bg2: "#FFE4E6",
        text: "#3B0013",
        soft: "#9F5060",
        grad: "linear-gradient(135deg,#9F0E2B,#E11D48,#FDA4AF)"
    },
    Slate: {
        c1: "#334155",
        c2: "#94A3B8",
        bg: "#F8FAFC",
        bg2: "#F1F5F9",
        text: "#0F172A",
        soft: "#64748B",
        grad: "linear-gradient(135deg,#0F172A,#334155,#94A3B8)"
    },
    Forest: {
        c1: "#16A34A",
        c2: "#86EFAC",
        bg: "#F0FDF4",
        bg2: "#DCFCE7",
        text: "#052E16",
        soft: "#4B7A5A",
        grad: "linear-gradient(135deg,#14532D,#16A34A,#86EFAC)"
    },
    Ocean: {
        c1: "#0284C7",
        c2: "#7DD3FC",
        bg: "#F0F9FF",
        bg2: "#E0F2FE",
        text: "#082F49",
        soft: "#3B7EA6",
        grad: "linear-gradient(135deg,#0C4A6E,#0284C7,#7DD3FC)"
    },
    Plum: {
        c1: "#9333EA",
        c2: "#D8B4FE",
        bg: "#FAF5FF",
        bg2: "#F3E8FF",
        text: "#3B0764",
        soft: "#7E5A9E",
        grad: "linear-gradient(135deg,#6B21A8,#9333EA,#D8B4FE)"
    },
    Copper: {
        c1: "#C2410C",
        c2: "#FDBA74",
        bg: "#FFF7ED",
        bg2: "#FFEDD5",
        text: "#431407",
        soft: "#92512A",
        grad: "linear-gradient(135deg,#7C2D12,#C2410C,#FDBA74)"
    },
    Sage: {
        c1: "#4D7C6F",
        c2: "#99D5C9",
        bg: "#F2FAF8",
        bg2: "#E0F2EE",
        text: "#0F2E28",
        soft: "#5E8A82",
        grad: "linear-gradient(135deg,#1D5045,#4D7C6F,#99D5C9)"
    },
};

// KPI icon paths (SVG path data)
const KPI_ICONS = {
    'Occupancy Rate': 'M3 11l9-8 9 8M5 10v10h14V10M10 20v-6h4v6',
    'Total Revenue': 'M12 3v18M17 7H9.5a2.5 2.5 0 000 5h5a2.5 2.5 0 010 5H6',
    'Rental Yield': 'M3 17l6-6 4 4 8-8M14 7h7v7',
    'Active Contracts': 'M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8zM14 3v5h5',
    'Churn Rate': 'M3 17l6-6 4 4 8-8M14 17h7v-7',
    'Renewals Due': 'M3 5h18M3 10h18M3 15h12',
};

// ─────────────────────────────────────────────────────────────────────────────
//  HELPERS
// ─────────────────────────────────────────────────────────────────────────────
function hexToRgba(hex, alpha) {
    const n = parseInt(hex.replace('#', ''), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

// ─────────────────────────────────────────────────────────────────────────────
//  MONEY FORMATTING  — single source of truth, mirrors Python format_money()
//  currencyInfo shape: { symbol, position: 'before'|'after', name: 'INR'|... }
// ─────────────────────────────────────────────────────────────────────────────
function formatMoney(val, currencyInfo) {
    const amount = Number(val) || 0;
    const abs = Math.abs(amount);
    // Graceful fallback — never crashes even if currencyInfo is missing
    const symbol   = (currencyInfo && currencyInfo.symbol)   || '';
    const position = (currencyInfo && currencyInfo.position) || 'before';
    const name     = String((currencyInfo && currencyInfo.name) || '').toUpperCase();
    const isInr    = name === 'INR';

    let body;
    if (isInr) {
        if (abs >= 10_000_000)   body = `${(amount / 10_000_000).toFixed(2)} Cr`;
        else if (abs >= 100_000) body = `${(amount / 100_000).toFixed(2)} Lakh`;
        else                     body = amount.toLocaleString('en-IN', { maximumFractionDigits: 0 });
    } else {
        if (abs >= 1_000_000_000)      body = `${(amount / 1_000_000_000).toFixed(2)} Billion`;
        else if (abs >= 1_000_000)     body = `${(amount / 1_000_000).toFixed(2)} Million`;
        else if (abs >= 1_000)         body = `${(amount / 1_000).toFixed(1)}K`;
        else                           body = amount.toLocaleString(undefined, { maximumFractionDigits: 0 });
    }

    return position === 'before' ? `${symbol} ${body}` : `${body} ${symbol}`;
}

// axisMoneyFormatter — for chart axis/tooltip callbacks whose values
// have been pre-divided by `scale` (default 100 000) by the backend SQL.
function axisMoneyFormatter(currencyInfo, scale = 100_000) {
    return (value) => formatMoney((Number(value) || 0) * scale, currencyInfo);
}

// ─────────────────────────────────────────────────────────────────────────────
//  DASHBOARD COMPONENT
// ─────────────────────────────────────────────────────────────────────────────
export class RentalDashboard extends Component {
    static template = "rental_management.Dashboard";
    static THEMES = THEMES;  // expose for template access

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");

        this.state = useState({
            loading: true,
            currentPage: "dashboard",
            theme: THEMES.Teal,
            themeName: "Teal",
            data: {},
            pageData: {},
            currency: {symbol: '₹', position: 'before', name: 'INR'},
            today: new Date().toLocaleDateString("en-IN", {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric"
            }),
        });

        this._charts = [];   // chart instances to destroy on update
        this._sparkCharts = [];

        // OWL 2 template expressions extract method references without binding,
        // so arrow-function handlers like () => navigateTo('x') lose `this`.
        this.navigateTo = this.navigateTo.bind(this);
        this.selectTheme = this.selectTheme.bind(this);
        this.onKpiClick = this.onKpiClick.bind(this);
        this.openOdooView = this.openOdooView.bind(this);
        this.onRightPanelKpiClick = this.onRightPanelKpiClick.bind(this);
        this.onActivityFeedClick = this.onActivityFeedClick.bind(this);
        this.onRentCollectionClick = this.onRentCollectionClick.bind(this);
        this.onSalesByTypeClick = this.onSalesByTypeClick.bind(this);
        this.onMaintenanceCategoryClick = this.onMaintenanceCategoryClick.bind(this);
        this.onLeadConvClick = this.onLeadConvClick.bind(this);
        this.onRegionClick = this.onRegionClick.bind(this);
        this.onOccupancyByTypeClick = this.onOccupancyByTypeClick.bind(this);
        this.onTicketTrendClick = this.onTicketTrendClick.bind(this);

        onMounted(async () => {
            await this._loadTheme();
            await this._loadDashboardData();
            this._applyThemeVars();
            await loadJS('/rental_management/static/src/js/lib/jquery.dataTables.min.js')
            await loadJS('/rental_management/static/src/js/lib/dataTables.bootstrap5.min.js')
            await loadJS('/rental_management/static/src/js/lib/echarts.min.js')
            await loadJS('/rental_management/static/src/js/lib/chart.umd.min.js')
            await loadJS('/rental_management/static/src/js/lib/leaflet.js')
        });

        onWillUnmount(() => this._destroyCharts());
    }

    // ── THEME ──────────────────────────────────────────────────────────────────
    async _loadTheme() {
        try {
            const res = await rpc("/rental/dashboard/theme", {});
            const name = res.theme || "Teal";
            this.state.themeName = name;
            this.state.theme = THEMES[name] || THEMES.Teal;
        } catch (_) { /* use default */
        }
    }

    _applyThemeVars() {
        const t = this.state.theme;
        const root = document.documentElement;
        root.style.setProperty("--p1", t.c1);
        root.style.setProperty("--p2", t.c2);
        root.style.setProperty("--grad", t.grad);
        root.style.setProperty("--bg", t.bg);
        root.style.setProperty("--bg2", t.bg2);
        root.style.setProperty("--text", t.text);
        root.style.setProperty("--soft", t.soft);
        root.style.setProperty("--p1-a", hexToRgba(t.c1, 0.10));
        root.style.setProperty("--p2-a", hexToRgba(t.c2, 0.14));
        root.style.setProperty("--grad-s", `linear-gradient(135deg,${hexToRgba(t.c1, 0.10)},${hexToRgba(t.c2, 0.10)})`);
    }

    async selectTheme(name) {
        this.state.themeName = name;
        this.state.theme = THEMES[name] || THEMES.Teal;
        this._applyThemeVars();
        this._destroyCharts();
        setTimeout(() => this._renderAllCharts(), 50);
        // Persist
        await rpc("/rental/dashboard/theme/save", {theme_name: name}).catch(() => {
        });
    }

    get themeList() {
        return Object.keys(THEMES);
    }

    getThemeColor(name) {
        return (THEMES[name] || THEMES.Teal).c1;
    }

    // ── DATA LOADING ───────────────────────────────────────────────────────────
    async _loadDashboardData() {
        this.state.loading = true;
        try {
            const data = await rpc("/rental/dashboard/data", {});
            this.state.data = data;
            if (data && data.currency) {
                this.state.currency = data.currency;
            }
        } catch (e) {
            console.error("Dashboard load error:", e);
        } finally {
            this.state.loading = false;
            setTimeout(() => this._renderAllCharts(), 100);
        }
    }

    async _loadPageData(page) {
        const endpoints = {
            properties: "/rental/dashboard/properties",
            rent: "/rental/dashboard/rent",         // unified Rental & Contracts
            sales: "/rental/dashboard/sales",
            maintenance: "/rental/dashboard/maintenance",
            brokers: "/rental/dashboard/brokers",
            map: "/rental/dashboard/map",
        };
        const ep = endpoints[page];
        if (!ep) return;
        try {
            const d = await rpc(ep, {});
            this.state.pageData = {...this.state.pageData, [page]: d};
        } catch (e) {
            console.error(`Page data error (${page}):`, e);
        }
    }

    // ── NAVIGATION ─────────────────────────────────────────────────────────────
    async navigateTo(page) {
        // Legacy deep links into the old Contracts page redirect to the
        // merged Rental & Contracts view.
        if (page === "contracts") {
            page = "rent";
        }
        this._destroyCharts();
        this.state.currentPage = page;
        if (!this.state.pageData[page] && page !== "dashboard") {
            await this._loadPageData(page);
        }
        setTimeout(() => this._renderPageCharts(page), 80);
    }

    // ── ODOO ACTION NAVIGATION ─────────────────────────────────────────────────
    openOdooView(model, domain = [], viewType = "list", name = "", res_id = false, groupby = [], context = {}) {
        let views = [[false, "form"]]
        if (viewType !== 'form') {
            views = [[false, viewType], [false, "form"]]
        }

        let doAction = {
            type: "ir.actions.act_window",
            name: name,
            res_model: model,
            views: views,
            domain,
            target: "current",
            context: {
            ...context,
            ...(groupby.length > 0 && groupby.reduce((acc, field) => {
                    acc[`search_default_${field}`] = 1;
                    return acc;
                }, {})),
            },
        }

        if (res_id) {
            doAction.res_id = res_id
        }
        this.action.doAction(doAction);
    }

    onKpiClick(kpi) {
        if (kpi && kpi.action) {
            this.openOdooView(kpi.action.model, kpi.action.domain || [], "list", kpi.action.name || "");
        }
    }

    // ── RIGHT PANEL CLICK HANDLERS ─────────────────────────────────────────────
    onRightPanelKpiClick(rk) {
        if (!rk) return;
        switch (rk.lbl) {
            case 'Portfolio Value':
                this.openOdooView('property.details', [], 'list', 'Properties');
                break;
            case 'Avg Lease Term':
                this.openOdooView('tenancy.details', [['contract_type', '=', 'running_contract']], 'list', 'Active Contracts');
                break;
            case 'Pending Invoices':
                this.openOdooView('account.move', [['move_type', '=', 'out_invoice'], ['state', '=', 'posted'], ['payment_state', 'not in', ['paid', 'in_payment']]], 'list', 'Pending Invoices');
                break;
        }
    }

    onActivityFeedClick(act) {
        if (!act || !act.model || !act.res_id) return;
        this.openOdooView(act.model, [['id', '=', act.res_id]], 'form', act.label || act.model, act.res_id);
    }

    onMaintenanceStatusClick(stageName) {
        const domain = [];
        if (stageName) {
            domain.push(['stage_id.name', '=', stageName]);
        }
        this.openOdooView('maintenance.request', domain, 'list', stageName ? `Maintenance — ${stageName}` : 'Maintenance Requests');
    }

    onRentCollectionClick(type) {
        if (!type) return;
        this.openOdooView('tenancy.details', [['property_id.type', '=', type.toLowerCase()], ['contract_type', '=', 'running_contract']], 'list', `Rent Contracts — ${type}`);
    }

    onSalesByTypeClick(type) {
        if (!type) return;
        this.openOdooView('property.vendor', [['property_id.type', '=', type.toLowerCase()]], 'list', `Sales — ${type}`);
    }

    onMaintenanceCategoryClick(cat) {
        if (!cat) return;
        this.openOdooView('maintenance.request', [['maintenance_type', '=', cat.toLowerCase()]], 'list', `Maintenance — ${cat}`);
    }

    onCommissionBreakdownClick(source) {
        if (!source) return;
        const lc = source.toLowerCase();
        if (lc.includes('sale')) {
            this.openOdooView('property.vendor', [], 'list', `Sale Commission — ${source}`);
        } else {
            this.openOdooView('tenancy.details', [], 'list', `Rental Commission — ${source}`);
        }
    }

    // ── CHART CLICK HANDLERS ───────────────────────────────────────────────────
    // Reverse-map display label → internal Selection value for property.type
    _typeFromLabel(label) {
        const map = {'Land': 'land', 'Residential': 'residential', 'Commercial': 'commercial', 'Industrial': 'industrial'};
        return map[label] || label;
    }

    onOccupancyByTypeClick(typeLabel, isOccupied) {
        if (!typeLabel) return;
        const internal = this._typeFromLabel(typeLabel);
        const domain = [['type', '=', internal]];
        if (isOccupied) domain.push(['stage', '=', 'on_lease']);
        else domain.push(['stage', '!=', 'on_lease']);
        this.openOdooView('property.details', domain, 'list', `Properties — ${typeLabel}`);
    }

    onRegionClick(region) {
        if (!region) return;
        let regionDomain = region === 'Unassigned' ? [['region_id', '=', false]] : [['region_id.name', '=', region]]
        this.openOdooView('property.details', regionDomain, 'list', `Properties — ${region}`);
    }

    onTicketTrendClick(status) {
        if (!status) return;
        const domain = [];
        if (status === 'Open') domain.push(['stage_id.done', '=', false]);
        else if (status === 'Resolved') domain.push(['stage_id.done', '=', true]);
        else if (status === 'Escalated') domain.push(['priority', '=', '3']);
        this.openOdooView('maintenance.request', domain, 'list', `Maintenance — ${status}`);
    }

    onLeadConvClick() {
        this.openOdooView('crm.lead', [['stage_id.is_won', '=', true]], 'list', 'Converted Leads');
    }

    onSankeyClick(params) {
        if (!params || !params.name) return;
        // Only handle node clicks (dataType undefined or 'node'), ignore edge clicks
        if (params.dataType === 'edge') return;
        const name = params.name;
        switch (name) {
            case 'Rent Income':
            case 'Deposit Income':
            case 'Maintenance Income':
            case 'Other Rent Income':
                this.openOdooView('rent.invoice', [], 'list', name);
                break;
            case 'Sales Income':
                this.openOdooView('property.vendor', [['stage', '=', 'sold']], 'list', 'Sales Income');
                break;
            case 'Total Revenue':
                this.openOdooView('account.move', [['move_type', '=', 'out_invoice'], ['state', '=', 'posted']], 'list', 'Total Revenue');
                break;
            case 'Broker Commission':
                this.openOdooView('property.vendor', [['is_any_broker', '=', true]], 'list', 'Broker Commissions');
                break;
            case 'Operating Expenses':
                this.openOdooView('account.move', [['move_type', '=', 'in_invoice'], ['state', '=', 'posted']], 'list', 'Operating Expenses');
                break;
            case 'Net Profit':
                this.openOdooView('account.move', [['move_type', '=', 'out_invoice'], ['state', '=', 'posted']], 'list', 'Revenue');
                break;
        }
    }

    onGaugeClick() {
        this.openOdooView('property.details', [['stage', '=', 'on_lease']], 'list', 'Occupied Properties');
    }

    onRevenueMixClick(typeName) {
        if (!typeName) return;
        const internal = this._typeFromLabel(typeName);
        this.openOdooView('property.details', [['type', '=', internal]], 'list', `Properties — ${typeName}`);
    }

    onLeadFunnelClick(stageName) {
        if (!stageName) return;
        this.openOdooView('crm.lead', [], 'list', `Leads — ${stageName}`);
    }

    onLeadSourceClick(source) {
        if (!source) return;
        this.openOdooView('crm.lead', [['source_id.name', '=', source]], 'list', `Leads — ${source}` );
    }

    onSalesFunnelClick(stageName) {
        if (!stageName) return;
        const stageMap = {'Booked': 'booked', 'Sold': 'sold', 'Refund': 'refund', 'Cancelled': 'cancel', 'Locked': 'locked'};
        const internal = stageMap[stageName];
        const domain = internal ? [['stage', '=', internal]] : [];
        this.openOdooView('property.vendor', domain, 'list', `Sale Contracts — ${stageName}`);
    }

    onPortfolioMixClick(typeName) {
        if (!typeName) return;
        const internal = this._typeFromLabel(typeName);
        this.openOdooView('property.details', [['type', '=', internal]], 'list', `Properties — ${typeName}`);
    }

    onCityDonutClick(city) {
        if (!city) return;
        this.openOdooView('property.details', [['city_id.name', '=', city]], 'list', `Properties — ${city}`);
    }

    // ── CHART EMPTY STATE ──────────────────────────────────────────────────────
    _showEmptyChart(el, msg = "No data available") {
        if (!el) return;
        el.innerHTML = `<div class="rm-chart-empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/></svg><span>${msg}</span></div>`;
    }

    // ── CHART DESTRUCTION ──────────────────────────────────────────────────────
    _destroyCharts() {
        this._charts.forEach(c => {
            try {
                c && typeof c.destroy === "function" && c.destroy();
            } catch (_) {
            }
            try {
                c && typeof c.dispose === "function" && c.dispose();
            } catch (_) {
            }
        });
        this._charts = [];
        this._sparkCharts.forEach(c => {
            try {
                c && c.destroy();
            } catch (_) {
            }
        });
        this._sparkCharts = [];
        if (this._mapInstance) {
            try { this._mapInstance.remove(); } catch (_) { /* noop */ }
            this._mapInstance = null;
        }
    }

    // ── CHART RENDERING ────────────────────────────────────────────────────────
    _renderAllCharts() {
        const d = this.state.data;
        if (!d || !d.kpis) return;
        this._renderSparklines(d.kpis);
        this._renderSankey(d.sankey);
        this._renderRadar(d.radar);
        this._renderForecast(d.forecast);
        this._renderGauge(d.occupancy_gauge);
        this._renderRevMix(d.revenue_mix);
        this._renderRpSpark(d.right_panel);
        this._renderMaintDonut(d.maintenance_status);
        this._renderLeads(d.leads);
    }

    _renderRightPanelCharts() {
        const d = this.state.data;
        if (!d) return;
        this._renderRpSpark(d.right_panel);
        this._renderMaintDonut(d.maintenance_status);
    }

    _renderPageCharts(page) {
        if (page === "dashboard") {
            this._renderAllCharts();
            return;
        }
        // Always re-draw right-panel widgets on every page navigation
        this._renderRightPanelCharts();

        const pd = this.state.pageData[page];
        if (!pd) return;
        switch (page) {
            case "properties":
                this._renderPropertyCharts(pd);
                break;
            case "rent":
                this._renderRentCharts(pd);
                this._renderContractCharts(pd);
                break;
            case "sales":
                this._renderSalesCharts(pd);
                break;
            case "maintenance":
                this._renderMaintenanceCharts(pd);
                break;
            case "brokers":
                this._renderBrokerCharts(pd);
                break;
            case "map":
                this._renderMapCharts(pd);
                break;
        }
    }

    // ── SPARK LINES (KPI mini charts) ──────────────────────────────────────────
    _renderSparklines(kpis) {
        if (!window.Chart) return;
        const t = this.state.theme;
        kpis.forEach((k, i) => {
            const el = document.getElementById(`sp${i}`);
            if (el && (!k.d || !k.d.length)) {
                this._showEmptyChart(el.parentElement || el, "No data");
                return;
            } else if (!el) {
                return;
            }
            const g = el.getContext("2d").createLinearGradient(0, 0, 0, 36);
            g.addColorStop(0, hexToRgba(t.c1, 0.28));
            g.addColorStop(1, hexToRgba(t.c2, 0));
            const ch = new Chart(el, {
                type: "line",
                data: {
                    labels: k.d.map((_, j) => j),
                    datasets: [{
                        data: k.d,
                        borderColor: t.c1,
                        backgroundColor: g,
                        borderWidth: 2,
                        tension: 0.42,
                        fill: true,
                        pointRadius: 0
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {legend: {display: false}, tooltip: {enabled: false}},
                    scales: {x: {display: false}, y: {display: false}},
                    animation: {duration: 600},
                },
            });
            this._sparkCharts.push(ch);
        });
    }

    // ── SANKEY ────────────────────────────────────────────────────────────────
    _renderSankey(data) {
        const el = document.getElementById("sankeyC");
        if (!el) return;
        if (!window.echarts || !data || !(data.links && data.links.length)) {
            this._showEmptyChart(el, "No revenue flow data yet");
            return;
        }
        const ec = echarts.init(el);
        const t = this.state.theme;
        const currency = this.state.currency;
        // The rebuilt _get_sankey returns raw monetary values (not /100_000),
        // so formatMoney is applied directly without the axis-scale factor.
        ec.setOption({
            tooltip: {
                trigger: "item",
                formatter: p => p.dataType === "edge"
                    ? `${p.data.source} → ${p.data.target}<br /><b>${formatMoney(p.data.value, currency)}</b>`
                    : `<b>${p.name}</b>`,
            },
            series: [{
                type: "sankey", left: 10, right: 140, top: 10, bottom: 10,
                nodeWidth: 14, nodeGap: 12, emphasis: {focus: "adjacency"},
                lineStyle: {color: "gradient", curveness: 0.55, opacity: 0.52},
                label: {fontFamily: "system-ui,sans-serif", fontSize: 11, fontWeight: 600, color: t.soft},
                data: data.data.map((d, i) => ({
                    ...d, itemStyle: {color: i < 2 ? t.c1 : i === 2 ? t.c2 : "#f59e0b"}
                })),
                links: data.links,
            }],
        });
        ec.on("click", (params) => this.onSankeyClick(params));
        this._charts.push(ec);
    }

    // ── RADAR ─────────────────────────────────────────────────────────────────
    _renderRadar(data) {
        const el = document.getElementById("radarC");
        if (!el) return;
        if (!window.echarts || !data || !(Array.isArray(data.current) && data.current.some(v => v))) {
            this._showEmptyChart(el, "No portfolio health data yet");
            return;
        }
        const ec = echarts.init(el);
        const t = this.state.theme;

        // Prefer indicators delivered by the backend so label changes only
        // need a single source edit. Fall back to the legacy hard-coded
        // set only if the server didn't include them.
        const indicators = (Array.isArray(data.indicators) && data.indicators.length)
            ? data.indicators
            : [
                {name: "Occupancy",   max: 100},
                {name: "Yield",       max: 100},
                {name: "Collection",  max: 100},
                {name: "Maintenance", max: 100},
                {name: "Contracts",   max: 100},
                {name: "Growth",      max: 100},
            ];

        ec.setOption({
            tooltip: {
                trigger: "item",
                formatter: (p) => {
                    const rows = indicators.map((ind, i) =>
                        `${ind.name}: <b>${(p.value[i] ?? 0).toFixed(1)}</b>`
                    ).join("<br/>");
                    return `<b>${p.seriesName}</b><br/>${rows}`;
                },
            },
            legend: {
                data: ["Current", "Previous"],
                bottom: 4,
                textStyle: {color: t.soft, fontSize: 10},
                itemWidth: 12, itemHeight: 6,
            },
            radar: {
                indicator: indicators,
                shape: "circle",
                radius: "62%",        // slightly smaller so labels have room
                center: ["50%", "45%"], // shift center upward
                splitNumber: 4,
                axisName: {color: t.soft, fontSize: 11, fontFamily: "system-ui,sans-serif"},
                splitLine: {lineStyle: {color: hexToRgba(t.c1, 0.12)}},
                splitArea: {show: true, areaStyle: {color: [hexToRgba(t.c1, 0.03), hexToRgba(t.c1, 0.07)]}},
                axisLine: {lineStyle: {color: hexToRgba(t.c1, 0.18)}},
            },
            series: [
                {
                    type: "radar", name: "Current", data: [{
                        value: data.current, name: "Current",
                        itemStyle: {color: t.c1}, areaStyle: {color: hexToRgba(t.c1, 0.22)},
                        lineStyle: {color: t.c1, width: 2.5},
                    }],
                },
                {
                    type: "radar", name: "Previous", data: [{
                        value: data.previous, name: "Previous",
                        itemStyle: {color: t.c2}, areaStyle: {color: hexToRgba(t.c2, 0.12)},
                        lineStyle: {color: t.c2, width: 2, type: "dashed"},
                    }],
                },
            ],
        });
        this._charts.push(ec);
    }

    // ── FORECAST LINE ─────────────────────────────────────────────────────────
    _renderForecast(data) {
        const el = document.getElementById("fcC");
        if (!el) return;
        if (!window.Chart || !data || !(data.labels && data.labels.length)) {
            this._showEmptyChart(el.parentElement || el, "No revenue forecast data yet");
            return;
        }
        const t = this.state.theme;
        const currency = this.state.currency;
        const moneyAxis = axisMoneyFormatter(currency);
        const g = el.getContext("2d").createLinearGradient(0, 0, 0, 280);
        g.addColorStop(0, hexToRgba(t.c1, 0.22));
        g.addColorStop(1, hexToRgba(t.c1, 0));
        const ch = new Chart(el, {
            type: "line",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: "Actuals", data: data.actuals, borderColor: t.c1, backgroundColor: g,
                        borderWidth: 2.5, tension: 0.4, fill: true, pointRadius: 3, pointBackgroundColor: t.c1
                    },
                    {
                        label: "Projected", data: data.projected, borderColor: t.c2, borderWidth: 2,
                        borderDash: [6, 3], tension: 0.4, fill: false, pointRadius: 3, pointBackgroundColor: t.c2
                    },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true, position: "top",
                        labels: {font: {family: "system-ui,sans-serif", size: 11}, boxWidth: 14, color: t.text}
                    }
                },
                scales: {
                    x: {grid: {color: hexToRgba(t.c1, 0.06)}, ticks: {font: {size: 10}, color: t.soft}},
                    y: {
                        grid: {color: hexToRgba(t.c1, 0.06)}, ticks: {
                            font: {size: 10}, color: t.soft,
                            callback: moneyAxis,
                        },
                    },
                },
            },
        });
        this._charts.push(ch);
    }

    // ── GAUGE ─────────────────────────────────────────────────────────────────
    // Layout responsibilities are split so that nothing overlaps:
    //   · axisLabel      → tick numbers, pushed outside arc via `distance: 0`
    //   · detail         → numeric value, vertically centred inside arc
    //   · title          → "Occupancy" label, placed BELOW the gauge
    //   · center/radius  → reserves breathing room under the arc for the title
    _renderGauge(data) {
        const el = document.getElementById("gaugeC");
        if (!el) return;
        if (!window.echarts || !data) {
            this._showEmptyChart(el, "No occupancy data yet");
            return;
        }
        const ec = echarts.init(el);
        const t = this.state.theme;
        ec.setOption({
            series: [{
                type: "gauge",
                startAngle: 210,
                endAngle: -30,
                min: 0,
                max: 100,
                center: ["50%", "62%"],
                radius: "82%",
                pointer: {show: false},
                progress: {show: true, width: 16, itemStyle: {color: t.c1}, roundCap: true},
                axisLine: {
                    lineStyle: {width: 16, color: [[1, hexToRgba(t.c1, 0.12)]], cap: "round"},
                },
                axisTick: {show: false},
                splitLine: {show: false},
                axisLabel: {show: false},
                anchor: {show: false},
                title: {
                    show: true,
                    fontSize: 12,
                    fontWeight: 600,
                    color: t.soft,
                    fontFamily: "system-ui, sans-serif",
                    offsetCenter: [0, "38%"],
                },
                detail: {
                    valueAnimation: true,
                    fontSize: 30,
                    fontWeight: 800,
                    fontFamily: "system-ui, sans-serif",
                    color: t.c1,
                    offsetCenter: [0, "0%"],
                    formatter: v => `${v}%`,
                },
                data: [{value: data.occupancy, name: "Occupancy"}],
            }],
        });
        ec.on("click", () => this.onGaugeClick());
        this._charts.push(ec);
    }

    // ── REVENUE MIX (Donut) ───────────────────────────────────────────────────
    _renderRevMix(data) {
        const el = document.getElementById("mixC");
        if (!el) return;
        if (!window.echarts || !data || !data.length || data.every(d => !d.revenue)) {
            this._showEmptyChart(el, "No revenue mix data yet");
            return;
        }
        const ec = echarts.init(el);
        const t = this.state.theme;
        const currency = this.state.currency;
        const toMoney = axisMoneyFormatter(currency);
        const colors = [t.c1, t.c2, hexToRgba(t.c1, 0.6), hexToRgba(t.c2, 0.7), "#f59e0b"];
        ec.setOption({
            tooltip: {formatter: p => `${p.name}: ${toMoney(p.value)} (${p.percent}%)`},
            legend: {bottom: 0, fontSize: 10, textStyle: {fontFamily: "system-ui,sans-serif", color: t.soft}},
            series: [{
                type: "pie", radius: ["40%", "68%"], center: ["50%", "46%"],
                avoidLabelOverlap: true, padAngle: 3, itemStyle: {borderRadius: 6, cursor: "pointer"},
                label: {show: false},
                data: data.map((d, i) => ({
                    name: (d.type || "other").replace("_", " "),
                    value: d.revenue,
                    itemStyle: {color: colors[i % colors.length]},
                })),
            }],
        });
        ec.on("click", (params) => this.onRevenueMixClick(params.name));
        this._charts.push(ec);
    }

    // ── RIGHT PANEL SPARKLINE ─────────────────────────────────────────────────
    _renderRpSpark(rp) {
        const el = document.getElementById("rpSparkCanvas");
        if (el && (!window.Chart || !rp || !rp.spark_data || !rp.spark_data.length)) {
            this._showEmptyChart(el.parentElement || el, "No data yet");
            return;
        } else if (!el) {
            return;
        }
        const t = this.state.theme;
        const g = el.getContext("2d").createLinearGradient(0, 0, 0, 90);
        g.addColorStop(0, hexToRgba(t.c1, 0.30));
        g.addColorStop(1, hexToRgba(t.c2, 0));
        const ch = new Chart(el, {
            type: "line",
            data: {
                labels: rp.spark_data.map((_, i) => i + 1),
                datasets: [{
                    data: rp.spark_data, borderColor: t.c1, backgroundColor: g,
                    borderWidth: 2.5, tension: 0.42, fill: true, pointRadius: 0
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {legend: {display: false}, tooltip: {enabled: false}},
                scales: {x: {display: false}, y: {display: false}},
            },
        });
        this._charts.push(ch);
    }

    // ── MAINTENANCE DONUT (right panel) ───────────────────────────────────────
    _renderMaintDonut(data) {
        const el = document.getElementById("rpDonut");
        if (el && (!window.echarts || !data || !data.length || data.every(d => !d.value))) {
            this._showEmptyChart(el, "No maintenance data yet");
            return;
        } else if (!el) {
            return;
        }
        const ec = echarts.init(el);
        const t = this.state.theme;
        ec.setOption({
            tooltip: {formatter: "{b}: {c} ({d}%)"},
            series: [{
                type: "pie", radius: ["36%", "62%"], center: ["50%", "50%"],
                itemStyle: {borderRadius: 6, cursor: "pointer"},
                label: {fontSize: 10, fontFamily: "system-ui,sans-serif", color: t.soft},
                data: data.map((item, i) => ({
                    name: item.name,
                    value: item.value,
                    itemStyle: {color: i === 0 ? "#1E8449" : i === 1 ? t.c1 : "#f59e0b"},
                })),
            }],
        });
        ec.on("click", (params) => this.onMaintenanceStatusClick(params.name));
        this._charts.push(ec);
    }

    // ── LEADS DASHBOARD ───────────────────────────────────────────────────────
    _renderLeads(data) {
        if (!data) return;
        const t = this.state.theme;

        // Funnel (New → Qualified → Won) — ECharts funnel
        const fEl = document.getElementById("leadFunnelC");
        if (fEl && (!window.echarts || !Array.isArray(data.funnel) || data.funnel.every(f => !f.value))) {
            this._showEmptyChart(fEl, "No pipeline data yet");
        } else if (fEl && window.echarts && Array.isArray(data.funnel)) {
            const ec = echarts.init(fEl);
            ec.setOption({
                tooltip: {trigger: "item", formatter: "{b}: <b>{c}</b>"},
                color: [t.c1, t.c2, "#f59e0b"],
                series: [{
                    type: "funnel",
                    left: "8%",
                    right: "8%",
                    top: 10,
                    bottom: 10,
                    min: 0,
                    minSize: "14%",
                    maxSize: "100%",
                    sort: "descending",
                    gap: 3,
                    label: {
                        show: true, position: "inside",
                        fontSize: 11, fontWeight: 700, color: "#fff",
                        formatter: "{b}\n{c}",
                    },
                    labelLine: {show: false},
                    itemStyle: {borderColor: "#fff", borderWidth: 2, borderRadius: 6, cursor: "pointer"},
                    data: data.funnel.map(f => ({name: f.stage, value: f.value || 0})),
                }],
            });
            this._charts.push(ec);
        }

        // Source-wise leads — horizontal bar with converted overlay
        const sEl = document.getElementById("leadSourceC");
        if (sEl && (!window.Chart || !Array.isArray(data.by_source) || !data.by_source.length)) {
            this._showEmptyChart(sEl.parentElement || sEl, "No lead source data yet");
        } else if (sEl && window.Chart && Array.isArray(data.by_source)) {
            const labels = data.by_source.map(s => s.source);
            const totals = data.by_source.map(s => s.leads);
            const converted = data.by_source.map(s => s.converted);
            const ch = new Chart(sEl, {
                type: "bar",
                data: {
                    labels,
                    datasets: [
                        {
                            label: "Leads",
                            data: totals,
                            backgroundColor: hexToRgba(t.c1, 0.25),
                            borderRadius: 4,
                        },
                        {
                            label: "Converted",
                            data: converted,
                            backgroundColor: t.c1,
                            borderRadius: 4,
                        },
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false, indexAxis: "y",
                    onClick: (evt, elements, chart) => {
                        if (elements.length) {
                            const label = chart.data.labels[elements[0].index];
                            this.onLeadSourceClick(label);
                        }
                    },
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {font: {size: 10}, boxWidth: 10, color: t.soft},
                        },
                    },
                    scales: {
                        x: {grid: {color: hexToRgba(t.c1, 0.06)}, ticks: {font: {size: 10}, color: t.soft}},
                        y: {grid: {display: false}, ticks: {font: {size: 10}, color: t.text}},
                    },
                },
            });
            this._charts.push(ch);
        }

        // Conversion rate gauge — clean single-ring donut with center %
        const cEl = document.getElementById("leadConvC");
        if (cEl && (!window.echarts || !data.totals)) {
            this._showEmptyChart(cEl, "No conversion data yet");
        } else if (cEl && window.echarts && data.totals) {
            const ec = echarts.init(cEl);
            const rate = data.totals.conversion_rate || 0;
            ec.setOption({
                tooltip: {show: false},
                series: [{
                    type: "gauge",
                    startAngle: 90,
                    endAngle: -270,
                    min: 0, max: 100,
                    center: ["50%", "55%"],
                    radius: "82%",
                    pointer: {show: false},
                    progress: {
                        show: true, overlap: false, roundCap: true,
                        clip: false, width: 12,
                        itemStyle: {color: t.c1},
                    },
                    axisLine: {lineStyle: {width: 12, color: [[1, hexToRgba(t.c1, 0.12)]]}},
                    splitLine: {show: false},
                    axisTick: {show: false},
                    axisLabel: {show: false},
                    title: {
                        show: true, offsetCenter: [0, "38%"],
                        fontSize: 10, color: t.soft, fontWeight: 500,
                    },
                    detail: {
                        valueAnimation: true, offsetCenter: [0, "0%"],
                        fontSize: 26, fontWeight: 800, color: t.c1,
                        formatter: v => `${v}%`,
                    },
                    data: [{value: rate, name: `${data.totals.won}/${(data.totals.won + data.totals.lost + data.totals.qualified) || 1} resolved`}],
                }],
            });
            ec.on("click", () => this.onLeadConvClick());
            this._charts.push(ec);
        }
    }

    // ── PROPERTY PAGE CHARTS ──────────────────────────────────────────────────
    _renderPropertyCharts(pd) {
        const t = this.state.theme;
        // Occupancy by type — stacked bar
        const ptEl = document.getElementById("ptypeC");
        if (ptEl && (!window.Chart || !pd.occupancy_by_type || !pd.occupancy_by_type.length)) {
            this._showEmptyChart(ptEl.parentElement || ptEl, "No occupancy data by type yet");
        } else if (ptEl && window.Chart && pd.occupancy_by_type) {
            const labels = pd.occupancy_by_type.map(d => d.type);
            const occ = pd.occupancy_by_type.map(d => d.occupied);
            const vacant = pd.occupancy_by_type.map(d => d.total - d.occupied);
            const ch = new Chart(ptEl, {
                type: "bar",
                data: {
                    labels,
                    datasets: [
                        {label: "Occupied", data: occ, backgroundColor: t.c1, borderRadius: 5},
                        {label: "Vacant", data: vacant, backgroundColor: hexToRgba(t.c1, 0.15), borderRadius: 5},
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {legend: {position: "top"}},
                    scales: {x: {stacked: true}, y: {stacked: true}},
                    onClick: (evt, elements, chart) => {
                        if (elements.length) {
                            const typeLabel = chart.data.labels[elements[0].index];
                            const isOccupied = elements[0].datasetIndex === 0;
                            this.onOccupancyByTypeClick(typeLabel, isOccupied);
                        }
                    },
                },
            });
            this._charts.push(ch);
        }
        // Portfolio mix — pie
        const pmEl = document.getElementById("pmixC");
        if (pmEl && (!window.echarts || !pd.portfolio_mix || !pd.portfolio_mix.length)) {
            this._showEmptyChart(pmEl, "No portfolio mix data yet");
        } else if (pmEl && window.echarts && pd.portfolio_mix) {
            const ec = echarts.init(pmEl);
            ec.setOption({
                tooltip: {},
                series: [{
                    type: "pie", radius: "65%",
                    data: pd.portfolio_mix.map((d, i) => ({
                        name: d.type, value: d.count,
                        itemStyle: {color: [t.c1, t.c2, "#f59e0b", "#6c63ff"][i % 4]},
                    })),
                    label: {fontFamily: "system-ui,sans-serif", fontSize: 11},
                }],
            });
            ec.on("click", (params) => this.onPortfolioMixClick(params.name));
            this._charts.push(ec);
        }
    }

    // ── RENT PAGE CHARTS ──────────────────────────────────────────────────────
    _renderRentCharts(pd) {
        const t = this.state.theme;
        const currency = this.state.currency;
        const moneyAxis = axisMoneyFormatter(currency);
        const rentEl = document.getElementById("rentC");
        if (rentEl && (!window.Chart || !pd.monthly_collection || !(pd.monthly_collection.labels && pd.monthly_collection.labels.length))) {
            this._showEmptyChart(rentEl.parentElement || rentEl, "No rent collection data yet");
        } else if (rentEl && window.Chart && pd.monthly_collection) {
            const mc = pd.monthly_collection;
            const g = rentEl.getContext("2d").createLinearGradient(0, 0, 0, 260);
            g.addColorStop(0, hexToRgba(t.c1, 0.20));
            g.addColorStop(1, hexToRgba(t.c1, 0));
            const ch = new Chart(rentEl, {
                type: "bar",
                data: {
                    labels: mc.labels,
                    datasets: [
                        {label: "Collected", data: mc.collected, backgroundColor: t.c1, borderRadius: 5},
                        {
                            label: "Outstanding",
                            data: mc.outstanding,
                            backgroundColor: hexToRgba(t.c1, 0.18),
                            borderRadius: 5,
                        },
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: {position: "top", labels: {color: t.soft, font: {size: 10}}},
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.dataset.label}: ${moneyAxis(ctx.parsed.y)}`,
                            },
                        },
                    },
                    scales: {
                        x: {grid: {display: false}, ticks: {color: t.soft, font: {size: 10}}},
                        y: {ticks: {callback: moneyAxis, color: t.soft, font: {size: 10}}},
                    },
                },
            });
            this._charts.push(ch);
        }
        // Collection rate donut
        const rdEl = document.getElementById("rentD");
        if (rdEl && (!window.echarts || !pd.collection_by_type || !pd.collection_by_type.length)) {
            this._showEmptyChart(rdEl, "No collection rate data yet");
        } else if (rdEl && window.echarts && pd.collection_by_type) {
            const ec = echarts.init(rdEl);
            ec.setOption({
                tooltip: {formatter: "{b}: {c}%"},
                series: [{
                    type: "pie", radius: ["40%", "68%"],
                    itemStyle: {cursor: "pointer"},
                    data: pd.collection_by_type.map((d, i) => ({
                        name: d.type, value: d.rate,
                        itemStyle: {color: [t.c1, t.c2, "#f59e0b"][i % 3]},
                    })),
                }],
            });
            ec.on("click", (params) => this.onRentCollectionClick(params.name));
            this._charts.push(ec);
        }
    }

    // ── SALES PAGE CHARTS ─────────────────────────────────────────────────────
    _renderSalesCharts(pd) {
        const t = this.state.theme;
        const funnelEl = document.getElementById("funnelC");
        if (funnelEl && (!window.echarts || !pd.funnel || pd.funnel.every(f => !f.count))) {
            this._showEmptyChart(funnelEl, "No sales pipeline data yet");
        } else if (funnelEl && window.echarts && pd.funnel) {
            const ec = echarts.init(funnelEl);
            ec.setOption({
                tooltip: {},
                series: [{
                    type: "funnel", left: "10%", width: "80%",
                    sort: "descending", gap: 6,
                    data: pd.funnel.map((d, i) => ({
                        name: d.stage, value: d.count,
                        itemStyle: {color: [t.c1, t.c2, "#f59e0b", "#e53935", "#6c63ff"][i % 5]},
                    })),
                    label: {fontFamily: "system-ui,sans-serif"},
                }],
            });
            ec.on("click", (params) => this.onSalesFunnelClick(params.name));
            this._charts.push(ec);
        }
        const sdEl = document.getElementById("salesD");
        if (sdEl && (!window.echarts || !pd.sales_by_type || !pd.sales_by_type.length)) {
            this._showEmptyChart(sdEl, "No sales by type data yet");
        } else if (sdEl && window.echarts && pd.sales_by_type) {
            const ec = echarts.init(sdEl);
            ec.setOption({
                tooltip: {},
                series: [{
                    type: "pie", radius: ["40%", "68%"],
                    itemStyle: {cursor: "pointer"},
                    data: pd.sales_by_type.map((d, i) => ({
                        name: d.type, value: d.count,
                        itemStyle: {color: [t.c1, t.c2, "#f59e0b", "#6c63ff"][i % 4]},
                    })),
                }],
            });
            ec.on("click", (params) => this.onSalesByTypeClick(params.name));
            this._charts.push(ec);
        }
    }

    // ── MAINTENANCE PAGE CHARTS ───────────────────────────────────────────────
    _renderMaintenanceCharts(pd) {
        const t = this.state.theme;
        const maintEl = document.getElementById("maintC");
        if (maintEl && (!window.Chart || !pd.ticket_trends || !(pd.ticket_trends.labels && pd.ticket_trends.labels.length))) {
            this._showEmptyChart(maintEl.parentElement || maintEl, "No maintenance ticket data yet");
        } else if (maintEl && window.Chart && pd.ticket_trends) {
            const tt = pd.ticket_trends;
            const ch = new Chart(maintEl, {
                type: "bar",
                data: {
                    labels: tt.labels,
                    datasets: [
                        {label: "Open", data: tt.open, backgroundColor: t.c1, borderRadius: 4},
                        {label: "Resolved", data: tt.resolved, backgroundColor: "#1E8449", borderRadius: 4},
                        {label: "Escalated", data: tt.escalated, backgroundColor: "#e53935", borderRadius: 4},
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {legend: {position: "top"}},
                    onClick: (evt, elements, chart) => {
                        if (elements.length) {
                            const datasetIndex = elements[0].datasetIndex;
                            const status = datasetIndex === 0 ? 'Open' : datasetIndex === 1 ? 'Resolved' : 'Escalated';
                            this.onTicketTrendClick(status);
                        }
                    },
                },
            });
            this._charts.push(ch);
        }
        const maintPEl = document.getElementById("maintP");
        if (maintPEl && (!window.echarts || !pd.by_category || !pd.by_category.length)) {
            this._showEmptyChart(maintPEl, "No category data yet");
        } else if (maintPEl && window.echarts && pd.by_category) {
            const ec = echarts.init(maintPEl);
            ec.setOption({
                tooltip: {},
                series: [{
                    type: "pie", radius: "65%",
                    itemStyle: {cursor: "pointer"},
                    data: pd.by_category.map((d, i) => ({
                        name: d.cat, value: d.count,
                        itemStyle: {color: [t.c1, t.c2, "#f59e0b", "#e53935"][i % 4]},
                    })),
                }],
            });
            ec.on("click", (params) => this.onMaintenanceCategoryClick(params.name));
            this._charts.push(ec);
        }
    }

    // ── CONTRACT PAGE CHARTS ──────────────────────────────────────────────────
    _renderContractCharts(pd) {
        const t = this.state.theme;
        // Gantt-style horizontal bars
        const ganttEl = document.getElementById("cgC");
        if (ganttEl && (!window.echarts || !pd.gantt || !pd.gantt.length)) {
            this._showEmptyChart(ganttEl, "No contract timeline data yet");
        } else if (ganttEl && window.echarts && pd.gantt) {
            const ec = echarts.init(ganttEl);
            const items = pd.gantt.slice(0, 20);
            const now = new Date().getTime();
            const colors = {active: t.c1, expiring: "#f59e0b", overdue: "#e53935"};
            ec.setOption({
                tooltip: {formatter: p => `${p.name}: ${p.data[1]} → ${p.data[2]}<br />Status: ${p.data[3]}`},
                xAxis: {type: "time", boundaryGap: false},
                yAxis: {data: items.map(c => c.tenant || c.seq), axisLabel: {fontSize: 10}},
                series: [{
                    type: "custom",
                    renderItem: (params, api) => {
                        const y = api.coord([0, api.value(0)])[1];
                        const x1 = api.coord([api.value(1), 0])[0];
                        const x2 = api.coord([api.value(2), 0])[0];
                        const h = 14;
                        return {
                            type: "rect", shape: {x: x1, y: y - h / 2, width: Math.max(x2 - x1, 4), height: h},
                            style: {fill: colors[api.value(3)] || t.c1, borderRadius: 3}
                        };
                    },
                    dimensions: ["tenant", "start", "end", "status"],
                    data: items.map((c, i) => [i, c.start, c.end || c.start, c.status]),
                    encode: {x: [1, 2], y: 0},
                }],
            });
            this._charts.push(ec);
        }
    }

    // ── BROKER PAGE CHARTS ────────────────────────────────────────────────────
    _renderBrokerCharts(pd) {
        const t = this.state.theme;
        const currency = this.state.currency;

        // ── Performance bar — horizontal, deals + commission dual series
        const bpEl = document.getElementById("bpC");
        if (bpEl && (!window.Chart || !pd.broker_performance || !pd.broker_performance.length)) {
            this._showEmptyChart(bpEl.parentElement || bpEl, "No broker performance data yet");
        } else if (bpEl && window.Chart && pd.broker_performance) {
            const bp = pd.broker_performance;
            const ch = new Chart(bpEl, {
                type: "bar",
                data: {
                    labels: bp.map(b => b.broker),
                    datasets: [
                        {
                            label: "Deals",
                            data: bp.map(b => b.deals),
                            backgroundColor: t.c1,
                            borderRadius: 4,
                        },
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false, indexAxis: "y",
                    plugins: {
                        tooltip: {
                            callbacks: {
                                afterLabel: (ctx) => {
                                    const broker = bp[ctx.dataIndex];
                                    return `Commission: ${formatMoney(broker.commission, currency)}`;
                                },
                            },
                        },
                    },
                },
            });
            this._charts.push(ch);
        }

        // ── Commission breakdown donut — Sale vs Rental split
        const cbEl = document.getElementById("bcD");
        if (cbEl && (!window.echarts || !pd.commission_breakdown || !(pd.commission_breakdown.by_source || []).some(s => (s.value || 0) > 0))) {
            this._showEmptyChart(cbEl, "No commission data yet");
        } else if (cbEl && window.echarts && pd.commission_breakdown) {
            const cb = pd.commission_breakdown;
            const bySource = (cb.by_source || []).filter(s => (s.value || 0) > 0);
            const totals = cb.totals || {};
            const ec = echarts.init(cbEl);
            ec.setOption({
                tooltip: {
                    trigger: "item",
                    formatter: (p) => {
                        const v = formatMoney(p.value, currency);
                        return `${p.name}<br/><b>${v}</b> (${p.percent}%)`;
                    },
                },
                legend: {
                    bottom: 0,
                    textStyle: {color: t.soft, fontSize: 10},
                    itemWidth: 10, itemHeight: 6,
                },
                color: [t.c1, t.c2],
                series: [{
                    type: "pie",
                    radius: ["55%", "78%"],
                    center: ["50%", "45%"],
                    avoidLabelOverlap: true,
                    label: {show: false},
                    labelLine: {show: false},
                    itemStyle: {cursor: "pointer"},
                    data: bySource,
                }],
                graphic: totals.total_formatted ? [{
                    type: "text",
                    left: "center",
                    top: "38%",
                    style: {
                        text: totals.total_formatted,
                        fill: t.text,
                        fontSize: 14,
                        fontWeight: 700,
                        fontFamily: "system-ui, sans-serif",
                    },
                }] : [],
            });
            this._charts.push(ec);
        }
    }

    // ── MAP PAGE CHARTS ───────────────────────────────────────────────────────
    _renderMapCharts(pd) {
        const t = this.state.theme;
        const currency = this.state.currency;

        // ── Property map — Leaflet + OpenStreetMap tiles
        // The map reuses a single #propertyMap div and is tracked in
        // `this._mapInstance` so theme swaps + page re-entries dispose it
        // cleanly (Leaflet throws "already initialized" otherwise).
        const mapEl = document.getElementById("propertyMap");
        if (mapEl && window.L) {
            if (this._mapInstance) {
                try { this._mapInstance.remove(); } catch (_) { /* noop */ }
                this._mapInstance = null;
            }

            const properties = (pd.properties || []).filter(
                p => typeof p.lat === "number" && typeof p.lng === "number"
                     && !Number.isNaN(p.lat) && !Number.isNaN(p.lng)
            );

            // Pick a centre: mean of the first cluster, else an India-wide fallback.
            const center = properties.length
                ? [
                    properties.reduce((a, p) => a + p.lat, 0) / properties.length,
                    properties.reduce((a, p) => a + p.lng, 0) / properties.length,
                ]
                : [20.5937, 78.9629];

            const map = L.map(mapEl, {
                center,
                scrollWheelZoom: true,
                zoomControl: true,
            });

            // OpenStreetMap standard tile layer — free, no API key required.
            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            }).addTo(map);

            const stagePillColor = {
                on_lease: "#1E8449", available: "#3949AB",
                booked:   "#B45309", sold:      "#607D8B",
            };

            const markers = properties.map(p => {
                const color = stagePillColor[p.stage] || t.c1;
                // A DivIcon lets us theme the marker without external SVG assets.
                const icon = L.divIcon({
                    className: "rm-map-marker",
                    html: `<span class="rm-map-pin" style="--pin:${color}"></span>`,
                    iconSize: [20, 26],
                    iconAnchor: [10, 26],
                    popupAnchor: [0, -24],
                });
                const price = p.stage === "sold" || p.stage === "booked" ? p.price : p.rent;
                const popup = `
                    <div class="rm-map-popup">
                        <div class="rm-map-popup-header">
                            <div class="rm-map-popup-name">${this._escapeHtml(p.name || "Untitled")}</div>
                            <span class="rm-pill rm-pill-${this.statusPill(p.stage)}">${this._escapeHtml(this.statusLabel(p.stage))}</span>
                        </div>
                        <div class="rm-map-popup-meta">
                            ${this._escapeHtml(p.type || "")}
                            ${p.city ? " · " + this._escapeHtml(p.city) : ""}
                        </div>
                        <div class="rm-map-popup-divider"></div>
                        <div class="rm-map-popup-row">
                            <span class="rm-map-popup-price-label">Price</span>
                            <span class="rm-map-popup-price">${formatMoney(price || 0, currency)}</span>
                        </div>
                    </div>`;
                return L.marker([p.lat, p.lng], {icon}).bindPopup(popup);
            });

            if (markers.length) {
                const group = L.featureGroup(markers).addTo(map);
                map.fitBounds(group.getBounds().pad(0.2), {maxZoom: 12});
            }

            // Ensure tiles render after animation completes (rare Leaflet quirk).
            setTimeout(() => map.invalidateSize(), 120);

            this._mapInstance = map;
        }

        // ── Regional distribution bar
        const regEl = document.getElementById("regC");
        if (regEl && (!window.Chart || !pd.regional || !pd.regional.length)) {
            this._showEmptyChart(regEl.parentElement || regEl, "No regional data yet");
        } else if (regEl && window.Chart && pd.regional) {
            const ch = new Chart(regEl, {
                type: "bar",
                data: {
                    labels: pd.regional.map(r => r.region),
                    datasets: [
                        {
                            label: "Total",
                            data: pd.regional.map(r => r.total),
                            backgroundColor: hexToRgba(t.c1, 0.15),
                            borderRadius: 4,
                        },
                        {
                            label: "Rented",
                            data: pd.regional.map(r => r.rented),
                            backgroundColor: t.c1,
                            borderRadius: 4,
                        },
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {legend: {position: "top", labels: {color: t.soft, font: {size: 10}}}},
                    onClick: (evt, elements, chart) => {
                        if (elements.length) {
                            const region = chart.data.labels[elements[0].index];
                            this.onRegionClick(region);
                        }
                    },
                },
            });
            this._charts.push(ch);
        }

        // ── City distribution donut
        const cityEl = document.getElementById("cityC");
        if (cityEl && (!window.echarts || !pd.city_distribution || !pd.city_distribution.length)) {
            this._showEmptyChart(cityEl, "No city distribution data yet");
        } else if (cityEl && window.echarts && pd.city_distribution) {
            const ec = echarts.init(cityEl);
            ec.setOption({
                tooltip: {formatter: "{b}: {c} ({d}%)"},
                legend: {bottom: 0, textStyle: {color: t.soft, fontSize: 10}},
                series: [{
                    type: "pie",
                    radius: ["35%", "68%"],
                    center: ["50%", "45%"],
                    itemStyle: {borderRadius: 4, borderColor: "#fff", borderWidth: 2, cursor: "pointer"},
                    label: {show: false},
                    data: pd.city_distribution.map((d, i) => ({
                        name: d.city, value: d.count,
                        itemStyle: {color: [t.c1, t.c2, "#f59e0b", "#6c63ff", "#e53935"][i % 5]},
                    })),
                }],
            });
            ec.on("click", (params) => this.onCityDonutClick(params.name));
            this._charts.push(ec);
        }
    }

    _escapeHtml(str) {
        return String(str ?? "").replace(/[&<>"']/g, ch => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        }[ch]));
    }

    // ── TEMPLATE HELPERS (used in XML) ─────────────────────────────────────────
    get kpis() {
        return this.state.data.kpis || [];
    }

    get sankey() {
        return this.state.data.sankey;
    }

    get rightPanel() {
        return this.state.data.right_panel || {};
    }

    get upcomingEvents() {
        return this.state.data.upcoming_events || [];
    }

    get activityFeed() {
        return this.state.data.activity_feed || [];
    }

    get glance() {
        return this.state.data.sidebar_glance || {};
    }

    get overdue() {
        return this.state.data.overdue_invoices || [];
    }

    get topProps() {
        return this.state.data.top_properties || [];
    }

    get leads() {
        return this.state.data.leads || {tiles: [], funnel: [], by_source: [], totals: {}};
    }

    leadTileDomain(tile) {
        // Mirrors _get_leads server-side bucketing so clicking a tile
        // drills into the exact same records the number represents.
        switch (tile.k) {
            case "Total Leads":
                return [["active", "=", true]];
            case "Qualified":
                return [["active", "=", true], ["probability", ">=", 50]];
            case "Converted (Won)":
                return [["stage_id.is_won", "=", true]];
            default:
                return [];
        }
    }

    get occupancyBreakdown() {
        const g = this.state.data.occupancy_gauge || {};
        const rented = g.rented || 0;
        const total = g.total || 0;
        return total ? `${rented} / ${total} units` : "No units yet";
    }

    get currencyInfo() {
        return this.state.currency;
    }

    money(v) {
        return formatMoney(v, this.state.currency);
    }

    get currentPageData() {
        return this.state.pageData[this.state.currentPage] || {};
    }

    fmtDate(d) {
        return d ? new Date(d).toLocaleDateString("en-IN") : "—";
    }

    statusPill(s) {
        const map = {
            running_contract: "g", new_contract: "b",
            cancel_contract: "r", close_contract: "r", expire_contract: "a",
            paid: "g", not_paid: "r", in_payment: "a",
            done: "g", active: "g", expiring: "a", overdue: "r",
        };
        return map[s] || "b";
    }

    statusLabel(s) {
        const map = {
            running_contract: "Running", new_contract: "Draft",
            cancel_contract: "Cancelled", close_contract: "Closed", expire_contract: "Expired",
            on_lease: "Rented", available: "Available", booked: "Booked", sold: "Sold",
            paid: "Paid", not_paid: "Overdue", in_payment: "In Payment",
            done: "Done", active: "Active", expiring: "Expiring", overdue: "Overdue",
        };
        return map[s] || String(s ?? "").replace(/_/g, " ");
    }

    priorityLabel(p) {
        return ["Low", "Normal", "High", "Critical"][parseInt(p) || 0];
    }

    daysDiff(d) {
        return daysDiff(d);
    }

    kpiTrend(kpi) {
        const isChurn = kpi.l === "Churn Rate";
        if (!kpi.tr) return null;
        const positive = isChurn ? kpi.tr < 0 : kpi.tr > 0;
        return {cls: positive ? "up" : "dn", arrow: positive ? "↑" : "↓", val: Math.abs(kpi.tr)};
    }
}

registry.category("actions").add("rental_management.dashboard_action_new", RentalDashboard);
