# -*- coding: utf-8 -*-
import base64
import io
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:
    openpyxl = None


class TenderJobCostInherit(models.Model):
    _inherit = 'tender.job.cost'

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string=_('Cost Center'),
        copy=False,
    )
    tender_item_code = fields.Char(
        string=_('Item Code'),
        copy=False,
    )
    project_id = fields.Many2one(
        'project.project',
        string=_('Tender Project'),
        copy=False,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string=_('Customer'),
        related='project_id.partner_id',
        store=True,
    )
    number = fields.Char(
        string=_('Internal Code'),
        readonly=True,
        default='New',
        copy=False,
    )
    is_breakdown_template = fields.Boolean(
        string=_('Use as Template'),
        copy=False,
        default=False,
        help='If checked, this breakdown can be picked as a template '
             'inside other breakdowns to load all its cost lines.',
    )
    template_source_id = fields.Many2one(
        'tender.job.cost',
        string=_('Load from Template'),
        copy=False,
        domain="[('is_breakdown_template', '=', True), ('id', '!=', id)]",
        help='Pick a breakdown marked as template, then press '
             '"Load from Template" to copy all its cost lines here.',
    )

    def action_load_from_template(self):
        """Copy ALL cost lines (materials, labour, equipment, expenses,
        subcontractor, deductions, allowances) from the selected template
        breakdown into this one, scaling quantities automatically by
        (this item qty / template item qty)."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Loading from a template is only allowed in draft state.'))
        if not self.template_source_id:
            raise UserError(_('Please select a template breakdown first.'))
        source = self.template_source_id

        source_lines = self.env['tender.job.cost.line'].search(
            [('job_cost_id', '=', source.id)])
        if not source_lines:
            raise UserError(_('The selected template has no cost lines.'))

        # Scale factor: template costed for its own item qty,
        # rescale to this breakdown's item qty (fallback 1:1)
        factor = 1.0
        if source.tender_item_qty and self.tender_item_qty:
            factor = self.tender_item_qty / source.tender_item_qty

        # Start clean: template load replaces current lines (no duplicates)
        self.env['tender.job.cost.line'].search(
            [('job_cost_id', '=', self.id)]).unlink()

        vals_list = []
        for src in source_lines:
            vals_list.append({
                'job_cost_id':  self.id,
                'product_id':   src.product_id.id,
                'description':  src.description,
                'date':         fields.Date.today(),
                'qty':          src.qty * factor,
                # fallback: lines saved without UoM take the product's UoM
                'uom_id':       src.uom_id.id or src.product_id.uom_id.id or False,
                'unit_price':   src.unit_price,
                'cost_actual':  src.cost_actual,
                'cost_per_day': src.cost_per_day,
                'no_of_days':   src.no_of_days,
                'flag':         src.flag,
            })
        self.env['tender.job.cost.line'].create(vals_list)

        if not self.notes_job:
            self.notes_job = source.notes_job
        return True

    # ── Customer portal access ──────────────────────────────────────────
    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/breakdowns/%s' % rec.id

    def action_open_customer_portal(self):
        """Open this breakdown's customer-portal page, where the customer
        can download the fillable template and upload it back."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.access_url,
            'target': 'self',
        }

    # ── Breakdown template (Excel) ────────────────────────────────────────
    # One sheet per cost type (mirroring the Materials / Labour / Expenses /
    # Equipment / Subcontractor tabs on the form) pre-filled with the
    # breakdown's current lines, plus a read-only product catalog sheet so
    # the customer can only enter products that exist in Odoo — matched
    # back on import by Internal Reference (كود المنتج / default_code).

    _BREAKDOWN_TYPES = [
        ('m', 'مواد - Materials', 'material'),
        ('l', 'عمالة - Labour', 'labour'),
        ('e', 'مصروفات - Expenses', 'expenses'),
        ('q', 'معدات - Equipment', 'equipment'),
        ('s', 'مقاول باطن - Subcontractor', 'subcontractor'),
    ]

    # Used to recognise which type a sheet belongs to when re-importing,
    # regardless of sheet ordering.
    _BREAKDOWN_SHEET_FLAGS = [
        ('m', ['مواد', 'materials', 'material']),
        ('l', ['عمالة', 'labour', 'labor']),
        ('e', ['مصروفات', 'expenses', 'expense']),
        ('q', ['معدات', 'equipment']),
        ('s', ['مقاول', 'subcontractor']),
    ]

    _BREAKDOWN_ALIASES = {
        'code':  ['code', 'كود', 'product code', 'كود المنتج', 'الكود',
                  'reference', 'internal reference'],
        'name':  ['product', 'المنتج', 'name', 'الاسم', 'اسم المنتج', 'item',
                  'البند', 'اسم البند'],
        'desc':  ['description', 'الوصف', 'وصف', 'desc'],
        'date':  ['date', 'التاريخ'],
        'qty':   ['qty', 'quantity', 'الكمية', 'كمية', 'الكمية المخططة',
                  'planned qty'],
        'uom':   ['uom', 'unit', 'وحدة', 'وحدة القياس'],
        'price': ['price', 'unit price', 'price per unit', 'السعر',
                  'سعر الوحدة', 'سعر الوحدة / price per unit'],
        'cost_actual': ['cost actual', 'التكلفة الفعلية'],
        'days':  ['days', 'no of days', 'no. of days', 'no of days ',
                  'عدد الايام', 'عدد الأيام', 'الايام'],
        'cost_per_day': ['cost per day', 'سعر اليوم', 'تكلفة اليوم', 'اليومية'],
    }

    _BREAKDOWN_UOM_MAP = {
        'م²': 'م²', 'م2': 'م²', 'متر مربع': 'م²', 'm²': 'م²', 'm2': 'م²', 'sqm': 'م²',
        'م³': 'م³', 'م3': 'م³', 'متر مكعب': 'م³', 'm³': 'م³', 'm3': 'م³', 'cbm': 'م³',
        'م': 'م', 'متر': 'م', 'م ط': 'م', 'م.ط': 'م', 'm': 'م', 'lm': 'م', 'meter': 'م',
        'كم': 'كم', 'كيلومتر': 'كم', 'km': 'كم',
        'طن': 'طن', 'ton': 'طن', 'tonne': 'طن', 't': 'طن',
        'كجم': 'كجم', 'كيلو': 'كجم', 'kg': 'كجم', 'kilogram': 'كجم',
        'جم': 'جم', 'g': 'جم', 'gram': 'جم',
        'لتر': 'لتر', 'l': 'لتر', 'liter': 'لتر',
        'وحدة': 'وحدة', 'قطعة': 'وحدة', 'عدد': 'وحدة',
        'unit': 'وحدة', 'units': 'وحدة', 'pcs': 'وحدة', 'pc': 'وحدة',
        'piece': 'وحدة', 'each': 'وحدة', 'ea': 'وحدة', 'no': 'وحدة', 'nos': 'وحدة',
        'ساعة': 'ساعة', 'hr': 'ساعة', 'h': 'ساعة', 'hour': 'ساعة',
        'يوم': 'يوم', 'day': 'يوم', 'days': 'يوم',
        'شهر': 'شهر', 'month': 'شهر',
        'دزينة': 'دزينة', 'dozen': 'دزينة',
        'رزمة': 'رزمة', 'pack': 'رزمة',
    }

    def _breakdown_cell_tokens(self, cell_val):
        if not cell_val:
            return []
        raw = str(cell_val).strip()
        tokens = []
        for part in raw.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            for sub in part.split('|'):
                for s in sub.split('/'):
                    t = s.strip().lower()
                    if t:
                        tokens.append(t)
        return tokens

    def _breakdown_detect_header(self, rows):
        for ridx, row in enumerate(rows[:20]):
            cell_tokens = [self._breakdown_cell_tokens(c) for c in row]
            found = {}
            for fld, als in self._BREAKDOWN_ALIASES.items():
                for ci, tokens in enumerate(cell_tokens):
                    if any(a in tokens for a in als):
                        found[fld] = ci
                        break
            if 'name' in found or 'code' in found:
                return ridx, found
        return None, {}

    def _breakdown_get_col(self, row, col_idx):
        if col_idx is None or col_idx < 0 or col_idx >= len(row):
            return ''
        v = row[col_idx]
        return str(v).strip() if v is not None else ''

    def _breakdown_to_float(self, raw, default=0.0):
        try:
            return float(str(raw).replace(',', '').strip())
        except (ValueError, TypeError):
            return default

    def _breakdown_find_product(self, code, name):
        """Strict lookup: when a product code is supplied it must match an
        existing product exactly (Internal Reference) — no fallback to
        name matching, so the customer cannot accidentally link the wrong
        product. Name matching is only used when no code was given."""
        Product = self.env['product.product']
        if code:
            return Product.search([('default_code', '=', code)], limit=1)
        if name:
            product = Product.search([('name', '=', name)], limit=1)
            if not product:
                matches = Product.search([('name', 'ilike', name)], limit=2)
                if len(matches) == 1:
                    product = matches
            return product
        return Product

    def _breakdown_flag_for_sheet_title(self, title):
        """Identify which cost type (flag) a worksheet belongs to, based on
        its title — used so re-imports work regardless of sheet order."""
        title_l = (title or '').strip().lower()
        if 'كتالوج' in title_l or 'catalog' in title_l:
            return None
        for flag, keywords in self._BREAKDOWN_SHEET_FLAGS:
            if any(k.lower() in title_l for k in keywords):
                return flag
        return None

    def _breakdown_to_date(self, raw):
        """Best-effort parsing of a date cell coming from Excel (may be a
        real datetime, or text in different formats)."""
        if hasattr(raw, 'date') and callable(getattr(raw, 'date')):
            return raw.date()
        if hasattr(raw, 'year') and hasattr(raw, 'month'):
            return raw
        raw = (str(raw) if raw is not None else '').strip()
        if not raw:
            return fields.Date.today()
        for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return fields.Date.today()

    def _breakdown_resolve_uom(self, raw_name, product):
        UoM = self.env['uom.uom']
        if raw_name:
            key = raw_name.strip().lower()
            canonical = self._BREAKDOWN_UOM_MAP.get(key) or self._BREAKDOWN_UOM_MAP.get(raw_name.strip())
            if canonical:
                uom = UoM.search([('name', '=', canonical)], limit=1)
                if uom:
                    return uom
            uom = UoM.search([('name', '=', raw_name.strip())], limit=1)
            if uom:
                return uom
            for token in self._breakdown_cell_tokens(raw_name):
                c2 = self._BREAKDOWN_UOM_MAP.get(token)
                if c2:
                    uom = UoM.search([('name', 'ilike', c2)], limit=1)
                    if uom:
                        return uom
        return product.uom_id if product and product.uom_id else False

    def _breakdown_read_all_sheets(self, file_b64):
        """Return a list of (sheet_title, rows) for every non-empty,
        visible worksheet in the uploaded file."""
        if openpyxl is None:
            raise UserError(_('openpyxl library is not installed.'))
        if not file_b64:
            raise UserError(_('Please upload the file first.'))
        data = base64.b64decode(file_b64)
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheets = [ws for ws in wb.worksheets
                  if getattr(ws, 'sheet_state', 'visible') == 'visible']
        if not sheets:
            sheets = wb.worksheets
        result = []
        for ws in sheets:
            rows = [list(row) for row in ws.iter_rows(values_only=True)]
            if not rows:
                continue
            result.append((ws.title, rows))
        return result

    # Columns shared by every type sheet; Labour gets two extra columns.
    _BREAKDOWN_BASE_COLS = [
        ("كود المنتج / Code", 16),
        ("المنتج / Product", 32),
        ("الوصف / Description", 32),
        ("التاريخ / Date", 13),
        ("الكمية المخططة / Planned Qty", 16),
        ("وحدة القياس / UoM", 14),
        ("سعر الوحدة / Price per Unit", 16),
        ("التكلفة الفعلية / Cost Actual", 16),
    ]
    _BREAKDOWN_LABOUR_EXTRA_COLS = [
        ("عدد الأيام / No. of Days", 14),
        ("سعر اليوم / Cost per Day", 16),
    ]

    def generate_breakdown_template_xlsx(self):
        """Build a styled RTL Excel workbook with one sheet per cost type
        (Materials / Labour / Expenses / Equipment / Subcontractor),
        pre-filled with this breakdown's current lines, plus a read-only
        product catalog sheet — returned as a base64 string."""
        self.ensure_one()
        if openpyxl is None:
            raise UserError(_('openpyxl is not installed. Contact your administrator.'))

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        H = "1F4E79"
        thin = Side(style="thin", color="BDC3C7")
        med = Side(style="medium", color=H)
        b_hdr = Border(left=med, right=med, top=med, bottom=med)
        lock_fill = PatternFill("solid", fgColor="EAECEE")

        Line = self.env['tender.job.cost.line']

        for flag, title, _field in self._BREAKDOWN_TYPES:
            cols = self._BREAKDOWN_BASE_COLS + (
                self._BREAKDOWN_LABOUR_EXTRA_COLS if flag == 'l' else [])
            ws = wb.create_sheet(title=title[:31])

            for ci, (hdr, width) in enumerate(cols, 1):
                cell = ws.cell(row=1, column=ci, value=hdr)
                cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor=H)
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = b_hdr
                ws.column_dimensions[get_column_letter(ci)].width = width
            ws.row_dimensions[1].height = 32

            existing = Line.search([
                ('job_cost_id', '=', self.id), ('flag', '=', flag)])

            row_idx = 2
            for line in existing:
                values = [
                    line.product_id.default_code or '',
                    line.product_id.display_name or '',
                    line.description or '',
                    line.date.strftime('%Y-%m-%d') if line.date else '',
                    line.qty,
                    line.uom_id.name or '',
                    line.unit_price,
                    line.cost_actual,
                ]
                if flag == 'l':
                    values += [line.no_of_days, line.cost_per_day]
                for ci, val in enumerate(values, 1):
                    cell = ws.cell(row=row_idx, column=ci, value=val)
                    cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
                    cell.font = Font(name="Calibri", size=10)
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                    if ci <= 2:
                        # كود المنتج / المنتج — لا تغيّر هذه القيم
                        cell.fill = lock_fill
                ws.row_dimensions[row_idx].height = 18
                row_idx += 1

            # extra empty rows for new items, with codes copied from the catalog sheet
            for r in range(row_idx, row_idx + 30):
                for ci in range(1, len(cols) + 1):
                    cell = ws.cell(row=r, column=ci, value="")
                    cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
                    cell.font = Font(name="Calibri", size=10)
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                    cell.fill = PatternFill("solid", fgColor="F4F6F7" if r % 2 == 0 else "FFFFFF")
                ws.row_dimensions[r].height = 18

            ws.freeze_panes = "A2"
            ws.sheet_view.rightToLeft = True

        # ── Product catalog (read-only reference for new rows) ──────────
        ws_cat = wb.create_sheet(title="كتالوج المنتجات - Catalog")
        cat_cols = [
            ("كود المنتج / Code", 16),
            ("المنتج / Product", 38),
            ("النوع / Type", 26),
            ("وحدة القياس / UoM", 14),
        ]
        for ci, (hdr, width) in enumerate(cat_cols, 1):
            cell = ws_cat.cell(row=1, column=ci, value=hdr)
            cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=H)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = b_hdr
            ws_cat.column_dimensions[get_column_letter(ci)].width = width
        ws_cat.row_dimensions[1].height = 30

        Product = self.env['product.product']
        domain = [
            ('default_code', '!=', False),
            '|', '|', '|', '|',
            ('product_tmpl_id.material', '=', True),
            ('product_tmpl_id.labour', '=', True),
            ('product_tmpl_id.expenses', '=', True),
            ('product_tmpl_id.equipment', '=', True),
            ('product_tmpl_id.subcontractor', '=', True),
        ]
        products = Product.search(domain, order='default_code', limit=2000)
        r = 2
        for p in products:
            tmpl = p.product_tmpl_id
            type_labels = [title.split(' - ')[0] for flag, title, field in self._BREAKDOWN_TYPES
                           if getattr(tmpl, field, False)]
            row_vals = [p.default_code or '', p.display_name,
                        ' / '.join(type_labels), p.uom_id.name or '']
            for ci, val in enumerate(row_vals, 1):
                cell = ws_cat.cell(row=r, column=ci, value=val)
                cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
                cell.font = Font(name="Calibri", size=10)
                cell.alignment = Alignment(horizontal="left", vertical="center")
                cell.fill = PatternFill("solid", fgColor="F4F6F7" if r % 2 == 0 else "FFFFFF")
            ws_cat.row_dimensions[r].height = 18
            r += 1
        ws_cat.freeze_panes = "A2"
        ws_cat.sheet_view.rightToLeft = True

        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue()).decode()

    def import_breakdown_lines_from_excel(self, file_b64):
        """Parse a filled-in breakdown template (same layout as
        generate_breakdown_template_xlsx): one sheet per cost type. For
        every sheet that contains at least one valid row, the existing
        lines of that type are replaced with the uploaded rows; products
        are matched strictly by Internal Reference (كود المنتج /
        default_code). Sheets left empty/unrecognised leave their type's
        existing lines untouched. Returns a dict with 'imported' /
        'skipped' counters and a list of 'notes'."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Import is only allowed while the breakdown is in draft state.'))

        sheets = self._breakdown_read_all_sheets(file_b64)
        if not sheets:
            raise UserError(_('The file is empty or contains no data.'))

        Line = self.env['tender.job.cost.line']
        imported, skipped, notes = 0, 0, []
        flag_vals = {}

        for title, rows in sheets:
            flag = self._breakdown_flag_for_sheet_title(title)
            if not flag:
                continue  # شيت الكتالوج أو شيت غير معروف — يتخطى

            hdr_idx, cols = self._breakdown_detect_header(rows)
            if hdr_idx is None:
                continue

            sheet_vals = []
            for i, row in enumerate(rows[hdr_idx + 1:], start=hdr_idx + 2):
                if all(v is None or str(v).strip() == '' for v in row):
                    continue
                code = self._breakdown_get_col(row, cols.get('code', -1))
                name = self._breakdown_get_col(row, cols.get('name', -1))
                if not code and not name:
                    continue
                product = self._breakdown_find_product(code, name)
                if not product:
                    skipped += 1
                    notes.append(_(
                        'Sheet "%(sheet)s", row %(row)s: product "%(ref)s" '
                        'not found in Odoo — skipped.',
                        sheet=title, row=i, ref=code or name))
                    continue

                qty = self._breakdown_to_float(
                    self._breakdown_get_col(row, cols.get('qty', -1)), 0.0)
                price = self._breakdown_to_float(
                    self._breakdown_get_col(row, cols.get('price', -1)),
                    product.standard_price)
                cost_actual = self._breakdown_to_float(
                    self._breakdown_get_col(row, cols.get('cost_actual', -1)),
                    product.standard_price)
                uom = self._breakdown_resolve_uom(
                    self._breakdown_get_col(row, cols.get('uom', -1)), product)
                days = int(self._breakdown_to_float(
                    self._breakdown_get_col(row, cols.get('days', -1)), 1.0) or 1)
                cost_per_day = self._breakdown_to_float(
                    self._breakdown_get_col(row, cols.get('cost_per_day', -1)), 0.0)
                if flag == 'l' and cost_per_day:
                    price = cost_per_day * days
                line_date = self._breakdown_to_date(
                    self._breakdown_get_col(row, cols.get('date', -1)))

                sheet_vals.append({
                    'job_cost_id': self.id,
                    'product_id': product.id,
                    'description': self._breakdown_get_col(row, cols.get('desc', -1))
                                    or name or product.name,
                    'date': line_date,
                    'qty': qty,
                    'uom_id': uom.id if uom else False,
                    'unit_price': price,
                    'cost_actual': cost_actual,
                    'cost_per_day': cost_per_day,
                    'no_of_days': days,
                    'flag': flag,
                })

            if sheet_vals:
                flag_vals[flag] = sheet_vals
                imported += len(sheet_vals)
            else:
                notes.append(_(
                    'Sheet "%(sheet)s": no valid rows found — existing '
                    'lines for this type were left unchanged.', sheet=title))

        if not flag_vals:
            raise UserError(_(
                'No valid rows found in any sheet. Please use the '
                'downloaded template without changing the column headers, '
                'and make sure the product code (كود المنتج) matches an '
                'existing product.'))

        for flag, vals_list in flag_vals.items():
            Line.search([('job_cost_id', '=', self.id), ('flag', '=', flag)]).unlink()
            Line.create(vals_list)

        return {'imported': imported, 'skipped': skipped, 'notes': notes}


    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.tender_item_code:
                parts.append(rec.tender_item_code)
            if rec.tender_item_name:
                parts.append(rec.tender_item_name)
            elif rec.name and rec.name != 'New':
                parts.append(rec.name)
            if not parts:
                parts.append(rec.number or '')
            rec.display_name = ' - '.join(parts)

    def action_approve(self):
        """Override approve to create analytic account (cost center) for the breakdown."""
        for rec in self:
            rec.write({'state': 'approve'})
            tender_line = self.env['project.tender'].search([
                ('template_id', '=', rec.id)
            ], limit=1)
            if not tender_line or not tender_line.project_id:
                continue
            project = tender_line.project_id
            if not rec.project_id:
                rec.project_id = project.id
            project_plan = project._ensure_analytic_plan()
            if not project_plan:
                continue
            if not rec.analytic_account_id:
                account = self.env['account.analytic.account'].create({
                    'name': rec.tender_item_name or rec.name,
                    'code': rec.tender_item_code or '',
                    'partner_id': project.partner_id.id if project.partner_id else False,
                    'plan_id': project_plan.id,
                    'company_id': rec.company_id.id or self.env.company.id,
                })
                rec.analytic_account_id = account.id
            distribution = {str(rec.analytic_account_id.id): 100.0}
            all_lines = (
                rec.job_cost_line_ids
                | rec.job_labour_line_ids
                | rec.job_equipment_line_ids
                | rec.job_expense_line_ids
                | rec.job_subcontractor_line_ids
            )
            # كتابة واحدة مجمّعة بدل الكتابة سطر بسطر — كل كتابة كانت
            # بتشغّل إعادة حساب + بحث في budget.line لكل لاين لوحده
            lines_to_update = all_lines.filtered(lambda l: not l.analytic_distribution)
            if lines_to_update:
                lines_to_update.write({'analytic_distribution': distribution})
            # إنشاء موازنة (Budget) بإجمالي تكلفة البريك داون على مركز التكلفة
            rec._create_budget_for_breakdown()

    def _create_budget_for_breakdown(self):
        """ينشئ Budget بقيمة إجمالي تكلفة البريك داون (jobcost_total)
        مربوطة بمركز التكلفة بتاعه — من غير تكرار لو فيه موازنة قبل كده."""
        self.ensure_one()
        if 'budget.analytic' not in self.env:
            return False  # موديول الموازنات مش متسطب
        if not self.analytic_account_id or not self.jobcost_total:
            return False
        # لو فيه سطر موازنة موجود لنفس مركز التكلفة ما نكررش
        existing = self.env['budget.line'].search(
            [('account_id', '=', self.analytic_account_id.id)], limit=1)
        if existing:
            return False
        project = self.project_id
        date_from = (project.date_start or fields.Date.today())
        date_to = project.date or fields.Date.add(date_from, years=1)
        if date_to < date_from:
            date_to = fields.Date.add(date_from, years=1)
        return self.env['budget.analytic'].create({
            'name': _('Budget - %s') % (self.tender_item_name or self.name or self.number),
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.company_id.id or self.env.company.id,
            'budget_line_ids': [(0, 0, {
                'account_id': self.analytic_account_id.id,
                'budget_amount': self.jobcost_total,
            })],
        })


class TenderJobCostLineInherit(models.Model):
    _inherit = 'tender.job.cost.line'

    @api.model_create_multi
    def create(self, vals_list):
        """Safety net: any line created without a UoM (Excel import, copy,
        template load, API...) gets the product's UoM automatically."""
        for vals in vals_list:
            if not vals.get('uom_id') and vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['uom_id'] = product.uom_id.id
        return super().create(vals_list)
