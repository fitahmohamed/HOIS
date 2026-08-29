# -*- coding: utf-8 -*-
import base64
from urllib.parse import quote

from odoo import http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.tools import consteq
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


def _attachment_disposition(filename):
    """Build a Content-Disposition header value, RFC 5987 encoded so
    non-ASCII (e.g. Arabic) filenames are handled correctly."""
    return "attachment; filename*=UTF-8''%s" % quote(filename)


class BreakdownTemplatePortal(CustomerPortal):
    """Customer-facing pages for the Breakdown (tender.job.cost) template:
    list the customer's breakdowns, download a blank/fillable Excel
    template and upload it back once filled in."""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'breakdown_count' in counters:
            partner = request.env.user.partner_id
            values['breakdown_count'] = request.env['tender.job.cost'].sudo().search_count(
                self._breakdown_get_records_domain(partner)
            )
        return values

    def _breakdown_get_records_domain(self, partner):
        return [('partner_id', 'child_of', [partner.commercial_partner_id.id])]

    def _breakdown_check_access(self, breakdown_id, access_token=None):
        job_cost_sudo = request.env['tender.job.cost'].sudo().browse(breakdown_id).exists()
        if not job_cost_sudo:
            raise MissingError(_("This breakdown does not exist."))

        if access_token and job_cost_sudo.access_token \
                and consteq(job_cost_sudo.access_token, access_token):
            return job_cost_sudo

        partner = request.env.user.partner_id
        if not job_cost_sudo.partner_id \
                or job_cost_sudo.partner_id.commercial_partner_id != partner.commercial_partner_id:
            raise AccessError(_("You do not have access to this breakdown."))
        return job_cost_sudo

    @http.route(['/my/breakdowns', '/my/breakdowns/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_breakdowns(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        JobCost = request.env['tender.job.cost'].sudo()
        domain = self._breakdown_get_records_domain(partner)

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'id desc'},
            'name': {'label': _('Reference'), 'order': 'number'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        breakdown_count = JobCost.search_count(domain)
        pager = portal_pager(
            url="/my/breakdowns",
            url_args={'sortby': sortby},
            total=breakdown_count,
            page=page,
            step=self._items_per_page,
        )
        breakdowns = JobCost.search(
            domain, order=order, limit=self._items_per_page, offset=pager['offset'])

        values.update({
            'breakdowns': breakdowns,
            'page_name': 'breakdown',
            'pager': pager,
            'default_url': '/my/breakdowns',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render('nthub_constructions_tenders.portal_my_breakdowns', values)

    @http.route(['/my/breakdowns/<int:breakdown_id>'], type='http', auth='user', website=True)
    def portal_breakdown_detail(self, breakdown_id, access_token=None, message=None, error=None, **kw):
        try:
            job_cost_sudo = self._breakdown_check_access(breakdown_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        lines = (
            job_cost_sudo.job_cost_line_ids
            | job_cost_sudo.job_labour_line_ids
            | job_cost_sudo.job_equipment_line_ids
            | job_cost_sudo.job_expense_line_ids
            | job_cost_sudo.job_subcontractor_line_ids
        )

        values = self._prepare_portal_layout_values()
        values.update({
            'breakdown': job_cost_sudo,
            'breakdown_lines': lines,
            'access_token': access_token,
            'page_name': 'breakdown',
            'message': message,
            'error': error,
        })
        return request.render('nthub_constructions_tenders.portal_breakdown_page', values)

    @http.route(['/my/breakdowns/<int:breakdown_id>/template'], type='http', auth='user')
    def portal_breakdown_download_template(self, breakdown_id, access_token=None, **kw):
        job_cost_sudo = self._breakdown_check_access(breakdown_id, access_token)
        file_b64 = job_cost_sudo.generate_breakdown_template_xlsx()
        filename = 'breakdown_template_%s.xlsx' % (job_cost_sudo.number or job_cost_sudo.id)
        return request.make_response(
            base64.b64decode(file_b64),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', _attachment_disposition(filename)),
            ],
        )

    @http.route(['/my/breakdowns/<int:breakdown_id>/upload'],
                type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def portal_breakdown_upload(self, breakdown_id, access_token=None, **post):
        job_cost_sudo = self._breakdown_check_access(breakdown_id, access_token)

        redirect_url = job_cost_sudo.access_url
        if access_token:
            redirect_url += '?access_token=%s' % access_token

        if job_cost_sudo.state != 'draft':
            return request.redirect(redirect_url + ('&' if access_token else '?') + 'error=state')

        upload = request.httprequest.files.get('breakdown_file')
        if not upload or not upload.filename:
            return request.redirect(redirect_url + ('&' if access_token else '?') + 'error=file')

        try:
            file_b64 = base64.b64encode(upload.read())
            job_cost_sudo.import_breakdown_lines_from_excel(file_b64)
        except Exception:
            return request.redirect(redirect_url + ('&' if access_token else '?') + 'error=parse')

        return request.redirect(redirect_url + ('&' if access_token else '?') + 'message=success')
