# -*- coding: utf-8 -*-
"""ويزارد اختيار: البنود اللي ليها بريك داون سابق —
المستخدم صاحب القرار: خد كوبي من آخر واحد أو أنشئ جديد فاضي."""
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class JobCostCopyChoiceWizard(models.TransientModel):
    _name = 'jobcost.copy.choice.wizard'
    _description = 'Breakdown Copy / New Choice'

    project_id = fields.Many2one('project.project', string=_('Tender Project'),
                                 required=True, readonly=True)
    line_ids = fields.One2many('jobcost.copy.choice.line', 'wizard_id',
                               string=_('Items'))

    def _apply(self):
        self.ensure_one()
        for wl in self.line_ids:
            line = wl.tender_line_id
            if not line or line.template_id:
                continue
            code = line.reference or line.item_id.code or ''
            if wl.choice == 'copy' and wl.source_id:
                self.project_id._copy_breakdown_for_line(wl.source_id, line)
            else:
                self.project_id._create_empty_breakdown_for_line(line, code)
        return {'type': 'ir.actions.act_window_close'}

    def action_apply(self):
        """تنفيذ اختيار كل سطر زي ما هو."""
        return self._apply()

    def action_copy_all(self):
        """خد كوبي للكل."""
        self.line_ids.write({'choice': 'copy'})
        return self._apply()

    def action_new_all(self):
        """أنشئ جديد للكل."""
        self.line_ids.write({'choice': 'new'})
        return self._apply()

    def action_cancel(self):
        """إلغاء — بيقفل الويزارد ويحدّث الشاشة عشان البريك داون
        اللي اتعمل للبنود الجديدة يظهر."""
        return {'type': 'ir.actions.act_window_close'}


class JobCostCopyChoiceLine(models.TransientModel):
    _name = 'jobcost.copy.choice.line'
    _description = 'Breakdown Copy / New Choice Line'

    wizard_id = fields.Many2one('jobcost.copy.choice.wizard',
                                ondelete='cascade')
    tender_line_id = fields.Many2one('project.tender', string=_('Tender Line'),
                                     readonly=True)
    item_name = fields.Char(related='tender_line_id.item_id.name',
                            string=_('Item'), readonly=True)
    item_code = fields.Char(related='tender_line_id.reference',
                            string=_('Code'), readonly=True)
    source_id = fields.Many2one('tender.job.cost',
                                string=_('Last Breakdown'), readonly=True)
    source_total = fields.Float(related='source_id.jobcost_total',
                                string=_('Its Total Cost'), readonly=True)
    choice = fields.Selection([
        ('copy', 'Copy Last One'),
        ('new',  'Create New'),
    ], string=_('Decision'), default='copy', required=True)
