# -*- coding: utf-8 -*-
# from odoo import http


# class NthubConstructionsTenders(http.Controller):
#     @http.route('/nthub_constructions_tenders/nthub_constructions_tenders', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/nthub_constructions_tenders/nthub_constructions_tenders/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('nthub_constructions_tenders.listing', {
#             'root': '/nthub_constructions_tenders/nthub_constructions_tenders',
#             'objects': http.request.env['nthub_constructions_tenders.nthub_constructions_tenders'].search([]),
#         })

#     @http.route('/nthub_constructions_tenders/nthub_constructions_tenders/objects/<model("nthub_constructions_tenders.nthub_constructions_tenders"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('nthub_constructions_tenders.object', {
#             'object': obj
#         })
