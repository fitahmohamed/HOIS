# -*- coding: utf-8 -*-
"""Wizard to import tender items from Excel or PDF — smart column mapping."""
import base64
import io
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:
    openpyxl = None

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


# ─────────────────────────────────────────────────────────────────────────────
# Wizard
# ─────────────────────────────────────────────────────────────────────────────

class ImportTenderItemsWizard(models.TransientModel):
    _name  = 'import.tender.items.wizard'
    _description = 'Import Tender Items from Excel / PDF'

    project_id = fields.Many2one('project.project', string=_('Project'),
                                 required=True, readonly=True)
    upload_file = fields.Binary(string=_('File (Excel / PDF)'), attachment=False)
    file_name   = fields.Char(string=_('File Name'))

    # state machine
    state = fields.Selection([
        ('upload',     'Upload File'),
        ('col_map',    'Map Columns'),
        ('uom_map',    'UoM Mapping'),
        ('preview',    'Preview'),
        ('done',       'Done'),
    ], default='upload', string=_('Step'))

    # column mapping
    col_code    = fields.Integer(string=_('Code Column'),          default=-1)
    col_name    = fields.Integer(string=_('Name Column'),          default=-1)
    col_desc    = fields.Integer(string=_('Description Column'),          default=-1)
    col_qty     = fields.Integer(string=_('Qty Column'),         default=-1)
    col_uom     = fields.Integer(string=_('UoM Column'),    default=-1)
    col_type    = fields.Integer(string=_('Type Column'),          default=-1)
    header_row  = fields.Integer(string=_('Header Row'),       default=0)

    # detected columns for selection
    detected_columns = fields.Char(string=_('Detected Columns'), readonly=True)

    # counters
    count_total    = fields.Integer(string=_('Total Rows'), readonly=True)
    count_ready    = fields.Integer(string=_('Ready'),          readonly=True)
    count_new      = fields.Integer(string=_('New'),          readonly=True)
    count_uom_diff = fields.Integer(string=_('UoM Conflicts'), readonly=True)
    count_section  = fields.Integer(string=_('Sections/Notes'), readonly=True)

    import_errors    = fields.Text(string=_('Warnings'), readonly=True)
    uom_mapping_ids  = fields.One2many('import.tender.uom.mapping', 'wizard_id',
                                       string=_('UoM Mapping'))
    preview_line_ids = fields.One2many('import.tender.items.preview', 'wizard_id',
                                       string=_('Preview Lines'))

    # ── UoM normalization map ─────────────────────────────────────────────────
    _UOM_MAP = {
        'م²':'م²','م2':'م²','متر مربع':'م²','m²':'م²','m2':'م²','sqm':'م²',
        'م³':'م³','م3':'م³','متر مكعب':'م³','m³':'م³','m3':'م³','cbm':'م³',
        'م':'م','متر':'م','م ط':'م','م.ط':'م','m':'م','lm':'م','meter':'م',
        'كم':'كم','كيلومتر':'كم','km':'كم',
        'طن':'طن','ton':'طن','tonne':'طن','t':'طن',
        'كجم':'كجم','كيلو':'كجم','kg':'كجم','kilogram':'كجم',
        'جم':'جم','g':'جم','gram':'جم',
        'لتر':'لتر','l':'لتر','liter':'لتر',
        'وحدة':'وحدة','قطعة':'وحدة','عدد':'وحدة',
        'unit':'وحدة','units':'وحدة','pcs':'وحدة','pc':'وحدة',
        'piece':'وحدة','each':'وحدة','ea':'وحدة','no':'وحدة','nos':'وحدة',
        'ساعة':'ساعة','hr':'ساعة','h':'ساعة','hour':'ساعة',
        'يوم':'يوم','day':'يوم','days':'يوم',
        'شهر':'شهر','month':'شهر',
        'دزينة':'دزينة','dozen':'دزينة',
        'رزمة':'رزمة','pack':'رزمة',
    }

    def _auto_resolve_uom(self, UoM, raw_name):
        if not raw_name:
            return False
        key = raw_name.strip().lower()
        canonical = self._UOM_MAP.get(key) or self._UOM_MAP.get(raw_name.strip())
        if canonical:
            uom = UoM.search([('name', '=', canonical)], limit=1)
            if uom: return uom
            uom = UoM.search([('name', 'ilike', canonical)], limit=1)
            if uom: return uom
        uom = UoM.search([('name', 'ilike', raw_name.strip())], limit=1)
        if uom: return uom
        for token in key.split():
            c2 = self._UOM_MAP.get(token)
            if c2:
                uom = UoM.search([('name', 'ilike', c2)], limit=1)
                if uom: return uom
        return False

    def _flag(self, type_str):
        m = {
            'material':'m','مواد':'m','labour':'l','labor':'l','عمالة':'l',
            'expenses':'e','مصروفات':'e','equipment':'q','معدات':'q',
            'subcontractor':'s','مقاول':'s',
        }
        return m.get(str(type_str).strip().lower(), 'm') if type_str else 'm'

    # ── Readers ───────────────────────────────────────────────────────────────

    def _read_excel_raw(self):
        """Read ALL rows from ALL visible sheets in the Excel file at once.

        الشيت الأول بياخد كل صفوفه (بما فيها الهيدر)، وأي شيت بعده
        بنكتشف صف الهيدر بتاعه ونتخطاه عشان ميتكررش وسط البيانات —
        فمش محتاج ترفع الملف شيت شيت.
        """
        if openpyxl is None:
            raise UserError(_('openpyxl library is not installed.'))
        data = base64.b64decode(self.upload_file)
        wb   = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheets = [ws for ws in wb.worksheets
                  if getattr(ws, 'sheet_state', 'visible') == 'visible']
        if not sheets:
            sheets = wb.worksheets
        all_rows = []
        for idx, ws in enumerate(sheets):
            rows = [list(row) for row in ws.iter_rows(values_only=True)]
            # تخطي الشيتات الفاضية تماماً
            if not rows or all(
                    all(v is None or str(v).strip() == '' for v in r)
                    for r in rows):
                continue
            if not all_rows:
                # أول شيت فيه بيانات — ياخد كل الصفوف (الهيدر هيتكتشف بعدين)
                all_rows.extend(rows)
            else:
                # الشيتات التالية — نشيل الهيدر بتاعها لو موجود
                hdr_idx, found = self._auto_detect_header(rows)
                start = hdr_idx + 1 if hdr_idx is not None else 0
                all_rows.extend(rows[start:])
        return all_rows

    def _read_pdf_raw(self):
        """Extract table rows from PDF using pdfplumber."""
        if not HAS_PDF:
            raise UserError(_('pdfplumber library is not installed. Contact your administrator.'))
        data = base64.b64decode(self.upload_file)
        rows = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    rows.extend(table)
        return rows

    def _get_raw_rows(self):
        fname = (self.file_name or '').lower()
        if fname.endswith('.pdf'):
            return self._read_pdf_raw()
        return self._read_excel_raw()

    def _cell_tokens(self, cell_val):
        if not cell_val: return []
        raw = str(cell_val).strip()
        tokens = []
        for part in raw.replace('\r\n','\n').replace('\r','\n').split('\n'):
            for sub in part.split('|'):
                for s in sub.split('/'):
                    t = s.strip().lower()
                    if t: tokens.append(t)
        return tokens

    def _auto_detect_header(self, rows):
        """Try to auto-detect header row and column mapping."""
        aliases = {
            'code': ['code','كود','item code','كود البند'],
            'name': ['name','item','اسم','اسم البند','البند','وصف البند'],
            'desc': ['description','الوصف','وصف','desc'],
            'qty':  ['qty','quantity','الكمية','كمية'],
            'uom':  ['uom','unit','وحدة','وحدة القياس'],
            'type': ['type','flag','النوع','نوع'],
        }
        for ridx, row in enumerate(rows[:20]):
            cell_tokens = [self._cell_tokens(c) for c in row]
            found = {}
            for fld, als in aliases.items():
                for ci, tokens in enumerate(cell_tokens):
                    if any(a in tokens for a in als):
                        found[fld] = ci
                        break
            if 'name' in found or 'code' in found:
                return ridx, found
        return None, {}

    # ── Step 1 → parse file ───────────────────────────────────────────────────

    def action_parse_file(self):
        self.ensure_one()
        if not self.upload_file:
            raise UserError(_('Please upload the file first.'))

        rows = self._get_raw_rows()
        if not rows:
            raise UserError(_('The file is empty or contains no data.'))

        header_row_idx, found = self._auto_detect_header(rows)

        # بناء قائمة الأعمدة المكتشفة للعرض
        header_row  = rows[header_row_idx] if header_row_idx is not None else rows[0]
        col_labels  = []
        for ci, cell in enumerate(header_row):
            label = str(cell).strip() if cell else f'عمود {ci+1}'
            col_labels.append(f"{ci}:{label}")
        detected = ' | '.join(col_labels[:15])

        self.write({
            'detected_columns': detected,
            'header_row':       header_row_idx if header_row_idx is not None else 0,
            'col_code':         found.get('code', -1),
            'col_name':         found.get('name', -1),
            'col_desc':         found.get('desc', -1),
            'col_qty':          found.get('qty',  -1),
            'col_uom':          found.get('uom',  -1),
            'col_type':         found.get('type', -1),
            'state':            'col_map',
        })
        return self._reopen()

    # ── Step 2 → UoM mapping ─────────────────────────────────────────────────

    def action_go_uom_map(self):
        self.ensure_one()
        rows = self._get_raw_rows()
        data_rows = rows[self.header_row + 1:]
        UoM = self.env['uom.uom']

        unique_uoms = {}
        for row in data_rows:
            raw = self._get_col(row, self.col_uom)
            if raw and raw not in unique_uoms:
                unique_uoms[raw] = self._auto_resolve_uom(UoM, raw)

        self.uom_mapping_ids.unlink()
        self.env['import.tender.uom.mapping'].create([{
            'wizard_id':    self.id,
            'raw_name':     raw,
            'uom_id':       uom.id if uom else False,
            'auto_matched': bool(uom),
        } for raw, uom in unique_uoms.items()])

        self.state = 'uom_map'
        return self._reopen()

    # ── Step 3 → preview ─────────────────────────────────────────────────────

    def _get_col(self, row, col_idx):
        if col_idx < 0 or col_idx >= len(row): return ''
        v = row[col_idx]
        return str(v).strip() if v is not None else ''

    def _is_section_row(self, row):
        """
        سطر بدون كمية ولا سعر — يُعامَل كعنوان أو ملاحظة.
        """
        qty = self._get_col(row, self.col_qty)
        try:
            float(qty)
            return False
        except (ValueError, TypeError):
            pass
        # لو فيه نص في اسم أو وصف بس مفيش كمية → section
        name = self._get_col(row, self.col_name) or self._get_col(row, self.col_code)
        return bool(name)

    def action_preview(self):
        self.ensure_one()
        rows     = self._get_raw_rows()
        data_rows = rows[self.header_row + 1:]

        uom_lookup = {m.raw_name: m.uom_id for m in self.uom_mapping_ids if m.uom_id}
        TenderItem = self.env['tender.item']

        self.preview_line_ids.unlink()
        preview_vals, errors = [], []
        sections = 0

        for i, row in enumerate(data_rows, start=self.header_row + 2):
            # تخطي الصفوف الفارغة تماماً
            if all((v is None or str(v).strip() == '') for v in row):
                continue

            code = self._get_col(row, self.col_code)
            name = self._get_col(row, self.col_name)
            desc = self._get_col(row, self.col_desc)
            qty_raw = self._get_col(row, self.col_qty)
            uom_raw = self._get_col(row, self.col_uom)
            type_raw = self._get_col(row, self.col_type)

            # section row
            if self._is_section_row(row):
                sections += 1
                preview_vals.append({
                    'wizard_id':  self.id,
                    'row_number': i,
                    'item_name':  name or code,
                    'item_code':  '',
                    'item_desc':  desc,
                    'qty':        0.0,
                    'flag':       'm',
                    'status':     'section',
                    'error_msg':  _('Section / Note'),
                })
                continue

            try:
                qty = float(qty_raw) if qty_raw else 1.0
            except ValueError:
                qty = 1.0

            uom = uom_lookup.get(uom_raw, False)

            # البحث عن البند — بالكود أولاً ثم بالاسم.
            # المعاينة بتقرا بس — مفيش إنشاء ولا تعديل غير بعد قرار المستخدم.
            item = False
            if code:
                item = TenderItem.search([('code', '=', code)], limit=1)
            if not item and name:
                item = TenderItem.search([('name', '=', name)], limit=1)

            status, note = 'ok', ''
            if not item:
                status, note = 'new', _('New item — will be created on import')
            elif uom and item.uom_id and uom.id != item.uom_id.id:
                # تعارض وحدة قياس → القرار للمستخدم، مفيش تعديل تلقائي
                status = 'uom_diff'
                note = _('File UoM (%(file_uom)s) differs from item UoM (%(item_uom)s) — choose a decision.',
                         file_uom=uom.name, item_uom=item.uom_id.name)

            if not uom and item and item.uom_id:
                uom = item.uom_id

            preview_vals.append({
                'wizard_id':    self.id,
                'row_number':   i,
                'item_id':      item.id if item else False,
                'item_name':    name or code,
                'item_code':    code,
                'item_desc':    desc,
                'qty':          qty,
                'uom_id':       uom.id if uom else False,
                'item_uom_id':  item.uom_id.id if item and item.uom_id else False,
                'uom_name':     uom_raw,
                'flag':         self._flag(type_raw),
                'status':       status,
                'uom_decision': 'keep_old' if status == 'uom_diff' else False,
                'error_msg':    note,
            })

        self.env['import.tender.items.preview'].create(preview_vals)
        ready    = sum(1 for p in preview_vals if p['status'] == 'ok')
        new_cnt  = sum(1 for p in preview_vals if p['status'] == 'new')
        uom_diff = sum(1 for p in preview_vals if p['status'] == 'uom_diff')

        self.write({
            'count_total':    len(preview_vals),
            'count_ready':    ready,
            'count_new':      new_cnt,
            'count_uom_diff': uom_diff,
            'count_section':  sections,
            'import_errors':  '\n'.join(errors) if errors else False,
            'state':          'preview',
        })
        return self._reopen()

    # ── Step 4 → import ──────────────────────────────────────────────────────

    def _resolve_import_line(self, l, TenderItem):
        """يرجع (item, uom, reference) للسطر حسب حالته وقرار المستخدم.

        - new: إنشاء بند جديد (هنا فقط — مش في المعاينة).
        - uom_diff: حسب قرار المستخدم:
            * keep_old → نفس البند بوحدة القياس القديمة بتاعته (مفيش تعديل).
            * new_item → بند جديد بوحدة قياس الملف (بكود مميز عشان البند
              القديم يفضل زي ما هو).
        - ok: البند زي ما هو.
        """
        if l.status == 'new' or (l.status in ('ok', 'uom_diff') and not l.item_id):
            create_vals = {'name': l.item_name}
            if l.item_code:
                create_vals['code'] = l.item_code
            if l.uom_id:
                create_vals['uom_id'] = l.uom_id.id
            item = TenderItem.create(create_vals)
            return item, l.uom_id, l.item_code

        item = l.item_id
        if l.status == 'uom_diff':
            if l.uom_decision == 'new_item':
                uom_suffix = l.uom_id.name if l.uom_id else 'uom'
                new_code = ('%s-%s' % (l.item_code, uom_suffix)
                            if l.item_code else False)
                new_name = (l.item_name if l.item_code
                            else '%s (%s)' % (l.item_name, uom_suffix))
                existing = TenderItem.search(
                    [('name', '=', new_name),
                     ('code', '=', new_code)], limit=1)
                item = existing or TenderItem.create({
                    'name':   new_name,
                    'code':   new_code,
                    'uom_id': l.uom_id.id if l.uom_id else False,
                })
                return item, l.uom_id, new_code or l.item_code
            # keep_old → وحدة قياس البند القديمة — البند نفسه ميتلمسش
            return item, item.uom_id, l.item_code

        # ok
        uom = l.uom_id or item.uom_id
        return item, uom, l.item_code

    def action_import(self):
        self.ensure_one()
        valid = self.preview_line_ids.filtered(
            lambda l: l.status in ('ok', 'new', 'uom_diff'))
        if not valid:
            raise UserError(_('No valid items to import.'))

        # تعارضات وحدة القياس لازم يتاخد فيها قرار قبل الاستيراد
        undecided = valid.filtered(
            lambda l: l.status == 'uom_diff' and not l.uom_decision)
        if undecided:
            raise UserError(_(
                'في %s بند وحدة القياس بتاعتهم في الملف مختلفة عن وحدة البند — '
                'اختار القرار لكل واحد (اعتماد القديمة أو إنشاء بند جديد) قبل الاستيراد.'
            ) % len(undecided))

        TenderItem = self.env['tender.item']
        today = fields.Date.today()
        tender_lines = []
        for l in valid:
            item, uom, reference = self._resolve_import_line(l, TenderItem)
            if not item:
                continue
            tender_lines.append((0, 0, {
                'item_id':     item.id,
                'description': l.item_desc if l.item_desc else l.item_name,
                'reference':   reference,
                'qty':         l.qty,
                'uom_id':      uom.id if uom else (
                               item.uom_id.id if item.uom_id else False),
                'flag':        l.flag,
                'date':        today,
            }))
        if not tender_lines:
            raise UserError(_('No valid items to import.'))
        self.project_id.write({'tender_ids': tender_lines})

        self.write({'state': 'done'})
        return self._reopen()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _reopen(self):
        return {
            'type':      'ir.actions.act_window',
            'res_model': self._name,
            'res_id':    self.id,
            'view_mode': 'form',
            'target':    'new',
        }

    def action_back_to_upload(self):
        self.preview_line_ids.unlink()
        self.uom_mapping_ids.unlink()
        self.write({
            'state':'upload','import_errors':False,
            'count_total':0,'count_ready':0,'count_new':0,
            'count_uom_diff':0,'count_section':0,
            'upload_file':False,'file_name':False,
        })
        return self._reopen()

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

    def action_download_template(self):
        return self.project_id.action_download_tender_template()


# ─────────────────────────────────────────────────────────────────────────────
# UoM Mapping
# ─────────────────────────────────────────────────────────────────────────────

class ImportTenderUomMapping(models.TransientModel):
    _name = 'import.tender.uom.mapping'
    _description = 'UoM Mapping for Import Wizard'

    wizard_id    = fields.Many2one('import.tender.items.wizard', ondelete='cascade')
    raw_name     = fields.Char(string=_('Raw UoM'), readonly=True)
    uom_id       = fields.Many2one('uom.uom', string=_('UoM in Odoo'))
    auto_matched = fields.Boolean(string=_('Auto Matched'), readonly=True)


# ─────────────────────────────────────────────────────────────────────────────
# Preview line
# ─────────────────────────────────────────────────────────────────────────────

class ImportTenderItemsPreview(models.TransientModel):
    _name = 'import.tender.items.preview'
    _description = 'Import Tender Items Preview Line'

    wizard_id  = fields.Many2one('import.tender.items.wizard', ondelete='cascade')
    row_number = fields.Integer(string=_('Row'),                 readonly=True)
    item_id    = fields.Many2one('tender.item', string=_('Item'))
    item_name  = fields.Char(string=_('Name in File'),       readonly=True)
    item_code  = fields.Char(string=_('Code in File'),       readonly=True)
    item_desc  = fields.Char(string=_('Description'),                readonly=True)
    qty        = fields.Float(string=_('Quantity'))
    uom_id     = fields.Many2one('uom.uom', string=_('Unit of Measure'))
    item_uom_id = fields.Many2one('uom.uom', string=_('Item Current UoM'),
                                  readonly=True)
    uom_name   = fields.Char(string=_('Raw UoM'),      readonly=True)
    flag       = fields.Selection([
        ('m','Material'),('l','Labour'),('e','Expenses'),('q','Equipment'),('s','Subcontractor'),
    ], string=_('Type'))
    status     = fields.Selection([
        ('ok','Existing'),('new','New'),('uom_diff','UoM Conflict'),
        ('section','Section'),('error','Error'),
    ], string=_('Status'), readonly=True)
    uom_decision = fields.Selection([
        ('keep_old', 'Keep Item UoM'),
        ('new_item', 'Create New Item with File UoM'),
    ], string=_('UoM Decision'))
    error_msg  = fields.Char(string=_('Note'), readonly=True)

    @api.onchange('item_id')
    def _onchange_item_id(self):
        for rec in self:
            if rec.item_id:
                rec.status = 'ok'
                if not rec.uom_id:
                    rec.uom_id = rec.item_id.uom_id


# ─────────────────────────────────────────────────────────────────────────────
# Import Breakdown (Job Cost) lines from Excel
# ─────────────────────────────────────────────────────────────────────────────

class ImportJobCostLinesWizard(models.TransientModel):
    _name = 'import.jobcost.lines.wizard'
    _description = 'Import Breakdown Lines from Excel'

    job_cost_id = fields.Many2one('tender.job.cost', string=_('Breakdown'),
                                  required=True, readonly=True)
    upload_file = fields.Binary(string=_('Excel File'), attachment=False)
    file_name   = fields.Char(string=_('File Name'))

    state = fields.Selection([
        ('upload', 'Upload'),
        ('done',   'Done'),
    ], default='upload', string=_('Step'))

    count_imported = fields.Integer(string=_('Imported Lines'), readonly=True)
    count_skipped  = fields.Integer(string=_('Skipped Rows'),   readonly=True)
    import_errors  = fields.Text(string=_('Notes'),    readonly=True)

    # ── import ───────────────────────────────────────────────────────────────

    def action_import(self):
        """نفس منطق استيراد بوابة العميل: شيت لكل نوع تكلفة (مواد/عمالة/
        مصروفات/معدات/مقاول باطن)، والربط بالمنتج بالكود (default_code)
        بشكل دقيق — أي كود غير موجود يتم تجاهل سطره مع ملاحظة."""
        self.ensure_one()
        if not self.upload_file:
            raise UserError(_('Please upload the file first.'))

        result = self.job_cost_id.import_breakdown_lines_from_excel(self.upload_file)

        self.write({
            'state':          'done',
            'count_imported': result.get('imported', 0),
            'count_skipped':  result.get('skipped', 0),
            'import_errors':  '\n'.join(result.get('notes', [])) if result.get('notes') else False,
        })
        return {
            'type':      'ir.actions.act_window',
            'res_model': self._name,
            'res_id':    self.id,
            'view_mode': 'form',
            'target':    'new',
        }

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

    def action_download_template(self):
        """تحميل القالب — نفس قالب بوابة العميل: شيت لكل نوع تكلفة (مواد /
        عمالة / مصروفات / معدات / مقاول باطن) معبأ ببنود البريك داون
        الحالية، بالإضافة لشيت كتالوج المنتجات."""
        file_b64 = self.job_cost_id.generate_breakdown_template_xlsx()
        att = self.env['ir.attachment'].create({
            'name': 'breakdown_template_%s.xlsx' % (self.job_cost_id.number or self.job_cost_id.id),
            'type': 'binary',
            'datas': file_b64,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': 'tender.job.cost',
            'res_id': self.job_cost_id.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{att.id}?download=true',
            'target': 'self',
        }
