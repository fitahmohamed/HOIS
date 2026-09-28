# -*- coding: utf-8 -*-
from odoo import models
from datetime import datetime, date as date_type


class LandlordCommissionReportAbstract(models.AbstractModel):
    _name = 'report.rental_management.report_landlord_commission_v2'
    _description = 'تقرير المالك'

    def _get_report_values(self, docids, data=None):
        if not data:
            data = {}

        # --- التواريخ ---
        d_from = False
        d_to = False
        df_str = data.get('df', '')
        dt_str = data.get('dt', '')
        if df_str:
            try:
                d_from = datetime.strptime(df_str, '%d/%m/%Y').date()
            except Exception:
                pass
        if dt_str:
            try:
                d_to = datetime.strptime(dt_str, '%d/%m/%Y').date()
            except Exception:
                pass

        # --- بيانات الويزارد لو موجود ---
        docs = self.env['landlord.commission.report']
        if docids:
            docs = self.env['landlord.commission.report'].browse(docids).exists()

        # لو الويزارد لسه موجود نجيب منه البيانات الناقصة
        if docs and (not d_from or not d_to):
            rec = docs[0]
            try:
                df_calc, dt_calc = rec._get_dates()
                d_from = d_from or df_calc
                d_to = d_to or dt_calc
                df_str = df_str or (d_from.strftime('%d/%m/%Y') if d_from else '')
                dt_str = dt_str or (d_to.strftime('%d/%m/%Y') if d_to else '')
            except Exception:
                pass

        # --- الوحدات ---
        property_ids = data.get('property_ids', [])
        all_units = self.env['property.details'].browse(property_ids).exists()
        vacant = all_units.filtered(lambda p: p.stage == 'available')
        rented = all_units.filtered(lambda p: p.stage == 'on_lease')

        # --- اسم العمارة والمالك ---
        subproject_name = data.get('subproject_name', '')
        landlord_name = data.get('landlord_name', '')
        if docs and not subproject_name:
            rec = docs[0]
            subproject_name = rec.subproject_id.name or ''
            landlord_name = landlord_name or rec.landlord_id.name or ''

        # --- العقود ---
        contracts = self.env['tenancy.details'].search([
            ('property_id', 'in', all_units.ids),
            ('rental_type', '=', 'commission'),
            ('contract_type', '=', 'running_contract'),
        ]) if all_units else self.env['tenancy.details']

        # --- حساب بيانات كل عقد ---
        contract_lines = []
        g_paid = g_total = g_over = g_comm = 0.0
        for c in contracts:
            if d_from and d_to:
                p_inv = c.rent_invoice_ids.filtered(
                    lambda i: i.invoice_date and d_from <= i.invoice_date <= d_to)
            else:
                p_inv = c.rent_invoice_ids

            paid = sum(p_inv.filtered(lambda i: i.payment_state == 'paid').mapped('amount'))
            total = sum(p_inv.mapped('amount'))
            overdue = sum(p_inv.filtered(lambda i: i.payment_state == 'not_paid').mapped('amount'))

            if d_from and d_to:
                comm = sum(c.commission_invoice_ids.filtered(
                    lambda m: m.state == 'posted' and m.invoice_date and d_from <= m.invoice_date <= d_to
                ).mapped('amount_total'))
            else:
                comm = sum(c.commission_invoice_ids.filtered(
                    lambda m: m.state == 'posted'
                ).mapped('amount_total'))

            g_paid += paid
            g_total += total
            g_over += overdue
            g_comm += comm

            contract_lines.append({
                'unit_name': c.property_id.name or '',
                'tenant_name': c.tenancy_id.name or '—',
                'monthly_rent': c.total_rent or 0.0,
                'inv_count': len(p_inv),
                'paid': paid,
                'remaining': total - paid,
                'overdue': overdue,
                'commission': comm,
            })

        # --- المصروفات ---
        expenses = data.get('expenses', [])
        total_expenses = data.get('total_expenses', 0.0)

        # --- تاريخ الطباعة ---
        print_date = date_type.today().strftime('%d/%m/%Y')

        # --- الصافي ---
        net_owner = g_paid - g_comm - total_expenses

        return {
            'doc_ids': docids or [],
            'doc_model': 'landlord.commission.report',
            'docs': docs,
            # بيانات مباشرة للقالب
            'df': df_str,
            'dt': dt_str,
            'subproject_name': subproject_name,
            'landlord_name': landlord_name,
            'all_units_count': len(all_units),
            'rented_count': len(rented),
            'vacant_count': len(vacant),
            'print_date': print_date,
            'contract_lines': contract_lines,
            'g_paid': g_paid,
            'g_total': g_total,
            'g_over': g_over,
            'g_comm': g_comm,
            'expenses': expenses,
            'total_expenses': total_expenses,
            'net_owner': net_owner,
            'total_inv_count': sum(cl['inv_count'] for cl in contract_lines),
        }
