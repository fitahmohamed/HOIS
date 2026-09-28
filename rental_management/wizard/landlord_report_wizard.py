# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import datetime
import io
import xlsxwriter
import base64


class LandlordCommissionReport(models.TransientModel):
    _name = 'landlord.commission.report'
    _description = 'تقرير المالك - إيجار بعمولة'

    subproject_id = fields.Many2one(
        'property.sub.project', string='العمارة',
        required=True,
        domain="[('rental_type', '=', 'commission')]"
    )
    landlord_id = fields.Many2one(
        related='subproject_id.landlord_id', string='المالك', readonly=True)

    # اختيار الشقق يدوياً
    property_ids = fields.Many2many(
        'property.details', string='الوحدات',
        domain="[('subproject_id', '=', subproject_id)]",
    )

    period_type = fields.Selection([
        ('this_month', 'الشهر الحالي'),
        ('this_year',  'السنة الحالية'),
        ('q1',         'الربع الأول'),
        ('q2',         'الربع الثاني'),
        ('q3',         'الربع الثالث'),
        ('q4',         'الربع الرابع'),
        ('custom',     'مخصص'),
    ], string='الفترة', required=True, default='this_month')

    date_from = fields.Date(string='من تاريخ')
    date_to   = fields.Date(string='إلى تاريخ')

    @api.onchange('subproject_id')
    def _onchange_subproject_id(self):
        """لما تختار العمارة يختار كل الشقق ديفولت"""
        if self.subproject_id:
            units = self.env['property.details'].search([
                ('subproject_id', '=', self.subproject_id.id)
            ])
            self.property_ids = units
        else:
            self.property_ids = False

    @api.onchange('period_type')
    def _onchange_period_type(self):
        if self.period_type == 'custom':
            self.date_from = False
            self.date_to   = False
        else:
            df, dt = self._compute_dates(self.period_type)
            self.date_from = df
            self.date_to   = dt

    def _compute_dates(self, period_type):
        today = fields.Date.today()
        year  = today.year
        if period_type == 'this_month':
            return today.replace(day=1), today.replace(day=1) + relativedelta(months=1, days=-1)
        elif period_type == 'this_year':
            return datetime.date(year, 1, 1), datetime.date(year, 12, 31)
        elif period_type == 'q1':
            return datetime.date(year, 1, 1), datetime.date(year, 3, 31)
        elif period_type == 'q2':
            return datetime.date(year, 4, 1), datetime.date(year, 6, 30)
        elif period_type == 'q3':
            return datetime.date(year, 7, 1), datetime.date(year, 9, 30)
        elif period_type == 'q4':
            return datetime.date(year, 10, 1), datetime.date(year, 12, 31)
        return self.date_from, self.date_to

    def _get_dates(self):
        if self.period_type != 'custom':
            return self._compute_dates(self.period_type)
        return self.date_from, self.date_to

    def _validate(self):
        df, dt = self._get_dates()
        if not df or not dt:
            raise UserError(_('من فضلك حدد الفترة الزمنية.'))
        if dt < df:
            raise UserError(_('تاريخ النهاية يجب أن يكون بعد تاريخ البداية.'))
        if not self.property_ids:
            raise UserError(_('من فضلك اختر وحدة واحدة على الأقل.'))
        return df, dt

    def _get_expenses(self, df, dt):
        """جلب المصروفات المرتبطة بمركز تكلفة العمارة"""
        analytic_account = self.subproject_id.analytic_account_id
        if not analytic_account:
            return [], 0.0

        analytic_id = str(analytic_account.id)

        # الخطوة 1: جيب كل سطور المصاريف والتكاليف في الفترة
        self.env.cr.execute("""
            SELECT
                aml.id,
                aml.date,
                aml.name            AS line_name,
                aml.debit,
                aml.analytic_distribution,
                am.name             AS move_name,
                am.ref              AS move_ref,
                acc.name            AS account_name,
                acc.note            AS account_code,
                acc.account_type
            FROM account_move_line aml
            JOIN account_move    am  ON am.id  = aml.move_id
            JOIN account_account acc ON acc.id = aml.account_id
            WHERE am.state = 'posted'
              AND am.show_in_owner_report = true
              AND aml.date >= %(df)s
              AND aml.date <= %(dt)s
              AND aml.debit > 0
              AND acc.account_type IN (
                  'expense',
                  'expense_other',
                  'expense_depreciation',
                  'expense_direct_cost'
              )
            ORDER BY aml.date
        """, {'df': df, 'dt': dt})

        rows = self.env.cr.dictfetchall()

        # الخطوة 2: فلتر على مركز التكلفة في Python
        import json
        result = []
        total = 0.0
        for row in rows:
            dist = row.get('analytic_distribution')
            if not dist:
                continue
            # psycopg2 بيرجع jsonb كـ dict مباشرة في أوديو 19
            if isinstance(dist, str):
                try:
                    dist = json.loads(dist)
                except Exception:
                    continue
            # مقارنة الـ ID كـ string لأن الـ keys في الـ JSON دايماً string
            if analytic_id not in [str(k) for k in dist.keys()]:
                continue

            amount = row['debit'] or 0.0
            description = row['line_name'] or row['move_ref'] or row['move_name'] or ''
            # acc.name ممكن يكون dict متعدد اللغات — نجيب en_US أو أول قيمة
            acc_name = row['account_name']
            if isinstance(acc_name, dict):
                acc_name = acc_name.get('en_US') or acc_name.get('ar_001') or next(iter(acc_name.values()), '')
            # account_code
            acc_code = row.get('account_code') or ''
            if isinstance(acc_code, dict):
                acc_code = acc_code.get('en_US') or acc_code.get('ar_001') or next(iter(acc_code.values()), '')
            result.append({
                'date': str(row['date']),
                'account': acc_name or '',
                'account_code': acc_code,
                'description': description,
                'move_name': row['move_name'] or '',
                'amount': amount,
            })
            total += amount
        return result, total

    def get_report_data(self):
        """بيرجع كل البيانات اللي التقرير محتاجها في dict واحد"""
        df, dt = self._get_dates()
        expenses, total_expenses = self._get_expenses(df, dt)
        return {
            'expenses': expenses,
            'total_expenses': total_expenses,
            'df': df,
            'dt': dt,
        }

    def get_expenses_for_report(self):
        """بترجع dict كامل بكل بيانات المصروفات للـ template — بدون arguments"""
        try:
            df, dt = self._get_dates()
        except Exception:
            return {'expenses': [], 'total_expenses': 0.0, 'df': '', 'dt': ''}
        if not df or not dt:
            return {'expenses': [], 'total_expenses': 0.0, 'df': '', 'dt': ''}
        expenses, total_expenses = self._get_expenses(df, dt)
        return {
            'expenses': expenses,
            'total_expenses': total_expenses,
            'df': df.strftime('%d/%m/%Y') if df else '',
            'dt': dt.strftime('%d/%m/%Y') if dt else '',
        }

    def get_report_df(self):
        try:
            df, _ = self._get_dates()
            return df.strftime('%d/%m/%Y') if df else ''
        except Exception:
            return ''

    def get_report_dt(self):
        try:
            _, dt = self._get_dates()
            return dt.strftime('%d/%m/%Y') if dt else ''
        except Exception:
            return ''

    def _build_report_ctx(self):
        """بناء dict البيانات المشترك بين HTML و PDF"""
        df, dt = self._validate()
        expenses, total_expenses = self._get_expenses(df, dt)
        return {
            'expenses': expenses,
            'total_expenses': total_expenses,
            'df': df.strftime('%d/%m/%Y') if df else '',
            'dt': dt.strftime('%d/%m/%Y') if dt else '',
            'property_ids': self.property_ids.ids,
            'landlord_name': self.landlord_id.name or '',
            'subproject_name': self.subproject_id.name or '',
        }

    def action_print_html(self):
        self.ensure_one()
        ctx = self._build_report_ctx()
        return self.env.ref(
            'rental_management.action_landlord_commission_report_v2'
        ).report_action(self, data=ctx)

    def action_print_pdf(self):
        self.ensure_one()
        ctx = self._build_report_ctx()
        report = self.env.ref('rental_management.action_landlord_commission_report_v2')
        old_type = report.report_type
        report.sudo().write({'report_type': 'qweb-pdf'})
        try:
            action = report.report_action(self, data=ctx)
        finally:
            report.sudo().write({'report_type': old_type})
        return action


    def action_print_excel(self):
        self.ensure_one()
        df, dt = self._validate()

        subproject = self.subproject_id
        all_units  = self.property_ids
        vacant     = all_units.filtered(lambda p: p.stage == 'available')
        rented     = all_units.filtered(lambda p: p.stage == 'on_lease')

        contracts  = self.env['tenancy.details'].search([
            ('property_id', 'in', all_units.ids),
            ('rental_type', '=', 'commission'),
            ('contract_type', '=', 'running_contract'),
        ])

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('تقرير المالك')
        ws.right_to_left()

        title_fmt  = wb.add_format({'bold': True, 'font_size': 14, 'align': 'center',
                                    'bg_color': '#1a3c6e', 'font_color': 'white', 'border': 1})
        hdr_fmt    = wb.add_format({'bold': True, 'font_size': 11, 'align': 'center',
                                    'bg_color': '#1a3c6e', 'font_color': 'white', 'border': 1})
        lbl_fmt    = wb.add_format({'bold': True, 'font_size': 11, 'border': 1, 'bg_color': '#f0f4ff'})
        val_fmt    = wb.add_format({'font_size': 11, 'border': 1, 'align': 'center'})
        money_fmt  = wb.add_format({'num_format': '#,##0.00', 'font_size': 11, 'border': 1, 'align': 'center'})
        green_fmt  = wb.add_format({'num_format': '#,##0.00', 'font_size': 11, 'border': 1,
                                    'align': 'center', 'font_color': '#27ae60'})
        red_fmt    = wb.add_format({'num_format': '#,##0.00', 'font_size': 11, 'border': 1,
                                    'align': 'center', 'font_color': '#c0392b'})
        total_fmt  = wb.add_format({'bold': True, 'font_size': 11, 'border': 1,
                                    'bg_color': '#1a3c6e', 'font_color': 'white',
                                    'num_format': '#,##0.00', 'align': 'center'})
        total_lbl  = wb.add_format({'bold': True, 'font_size': 11, 'border': 1,
                                    'bg_color': '#1a3c6e', 'font_color': 'white', 'align': 'center'})
        sum_lbl    = wb.add_format({'bold': True, 'font_size': 11, 'border': 1, 'bg_color': '#f0f4ff'})
        sum_val    = wb.add_format({'num_format': '#,##0.00', 'font_size': 11, 'border': 1,
                                    'align': 'center', 'bold': True})

        ws.set_column('A:A', 5)
        ws.set_column('B:B', 20)
        ws.set_column('C:C', 22)
        ws.set_column('D:I', 14)

        period_label = dict(self._fields['period_type'].selection).get(self.period_type, '')

        ws.merge_range('A1:I1', f'كشف حساب المالك — {subproject.name}', title_fmt)
        ws.merge_range('A2:I2',
            f'المالك: {self.landlord_id.name or "—"}    |    الفترة: {period_label}    |    '
            f'{df.strftime("%d/%m/%Y")} — {dt.strftime("%d/%m/%Y")}', lbl_fmt)
        ws.merge_range('A3:I3',
            f'إجمالي الوحدات المختارة: {len(all_units)}   |   الموجر: {len(rented)}   |   الشاغر: {len(vacant)}', lbl_fmt)

        row = 4
        headers = ['#', 'الوحدة', 'المستأجر', 'الإيجار الشهري',
                   'عدد الدفعات', 'المسدد', 'المتبقي', 'المتعثرات', 'العمولة']
        for col, h in enumerate(headers):
            ws.write(row, col, h, hdr_fmt)

        row += 1
        g_paid = g_total = g_over = g_comm = 0
        for i, c in enumerate(contracts):
            p_inv   = c.rent_invoice_ids.filtered(lambda x: x.invoice_date and df <= x.invoice_date <= dt)
            paid    = sum(p_inv.filtered(lambda x: x.payment_state == 'paid').mapped('amount'))
            total   = sum(p_inv.mapped('amount'))
            overdue = sum(p_inv.filtered(lambda x: x.payment_state == 'not_paid').mapped('amount'))
            comm    = sum(c.commission_invoice_ids.filtered(
                lambda m: m.state == 'posted' and m.invoice_date and df <= m.invoice_date <= dt
            ).mapped('amount_total'))
            g_paid += paid; g_total += total; g_over += overdue; g_comm += comm

            alt = wb.add_format({'font_size': 11, 'border': 1, 'align': 'center',
                                 'bg_color': '#f7f9fc' if i % 2 else '#ffffff'})
            alt_m = wb.add_format({'num_format': '#,##0.00', 'font_size': 11, 'border': 1,
                                   'align': 'center', 'bg_color': '#f7f9fc' if i % 2 else '#ffffff'})
            ws.write(row, 0, i + 1, alt)
            ws.write(row, 1, c.property_id.name, alt)
            ws.write(row, 2, c.tenancy_id.name or '—', alt)
            ws.write(row, 3, c.total_rent, alt_m)
            ws.write(row, 4, len(p_inv), alt)
            ws.write(row, 5, paid, green_fmt)
            ws.write(row, 6, total - paid, red_fmt)
            ws.write(row, 7, overdue, red_fmt)
            ws.write(row, 8, comm, alt_m)
            row += 1

        ws.write(row, 0, 'الإجمالي', total_lbl)
        ws.merge_range(row, 1, row, 3, '', total_lbl)
        ws.write(row, 4, len(contracts.mapped('rent_invoice_ids').filtered(
            lambda i: i.invoice_date and df <= i.invoice_date <= dt)), total_fmt)
        ws.write(row, 5, g_paid, total_fmt)
        ws.write(row, 6, g_total - g_paid, total_fmt)
        ws.write(row, 7, g_over, total_fmt)
        ws.write(row, 8, g_comm, total_fmt)

        row += 2
        # ====== جدول المصروفات ======
        expenses, total_expenses = self._get_expenses(df, dt)
        exp_hdr = wb.add_format({'bold': True, 'font_size': 11, 'align': 'center',
                                 'bg_color': '#7b2d2d', 'font_color': 'white', 'border': 1})
        exp_lbl = wb.add_format({'font_size': 11, 'border': 1, 'bg_color': '#fff5f5'})
        exp_val = wb.add_format({'num_format': '#,##0.00', 'font_size': 11, 'border': 1,
                                 'align': 'center', 'bg_color': '#fff5f5'})
        exp_date = wb.add_format({'num_format': 'dd/mm/yyyy', 'font_size': 11, 'border': 1,
                                  'align': 'center', 'bg_color': '#fff5f5'})

        ws.merge_range(row, 0, row, 8, 'المصروفات', exp_hdr)
        row += 1
        exp_headers = ['#', 'التاريخ', 'القيد', 'الحساب', 'كود الحساب', 'البيان', '', '', 'المبلغ']
        for col, h in enumerate(exp_headers):
            ws.write(row, col, h, hdr_fmt)
        row += 1
        for i, exp in enumerate(expenses):
            bg = '#fff5f5' if i % 2 == 0 else '#ffffff'
            alt_e  = wb.add_format({'font_size': 11, 'border': 1, 'align': 'center', 'bg_color': bg})
            alt_el = wb.add_format({'font_size': 11, 'border': 1, 'bg_color': bg})
            alt_em = wb.add_format({'num_format': '#,##0.00', 'font_size': 11, 'border': 1,
                                    'align': 'center', 'bg_color': bg})
            alt_ed = wb.add_format({'num_format': 'dd/mm/yyyy', 'font_size': 11, 'border': 1,
                                    'align': 'center', 'bg_color': bg})
            ws.write(row, 0, i + 1, alt_e)
            ws.write_datetime(row, 1, exp['date'], alt_ed) if hasattr(exp['date'], 'strftime') else ws.write(row, 1, str(exp['date']), alt_e)
            ws.write(row, 2, exp['move_name'], alt_e)
            ws.write(row, 3, exp['account'], alt_el)
            ws.write(row, 4, exp['account_code'], alt_e)
            ws.merge_range(row, 5, row, 7, exp['description'], alt_el)
            ws.write(row, 8, exp['amount'], alt_em)
            row += 1

        # إجمالي المصروفات
        ws.merge_range(row, 0, row, 7, 'إجمالي المصروفات', total_lbl)
        ws.write(row, 8, total_expenses, total_fmt)
        row += 2

        # ====== الملخص المالي ======
        for label, val in [
            ('التوريد (إجمالي المحصل)', g_paid),
            ('العمولة', g_comm),
            ('المصروفات', total_expenses),
            ('الصافي للمالك', g_paid - g_comm - total_expenses),
        ]:
            ws.merge_range(row, 0, row, 3, label, sum_lbl)
            ws.merge_range(row, 4, row, 8, val, sum_val)
            row += 1

        wb.close()
        output.seek(0)
        xlsx_data = base64.b64encode(output.read()).decode()
        fname = f'تقرير_المالك_{subproject.name}_{df}.xlsx'
    