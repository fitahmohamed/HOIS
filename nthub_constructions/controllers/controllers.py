# -*- coding: utf-8 -*-
# from odoo import http


# class NthubConstructions(http.Controller):
#     @http.route('/nthub_constructions/nthub_constructions', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/nthub_constructions/nthub_constructions/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('nthub_constructions.listing', {
#             'root': '/nthub_constructions/nthub_constructions',
#             'objects': http.request.env['nthub_constructions.nthub_constructions'].search([]),
#         })

#     @http.route('/nthub_constructions/nthub_constructions/objects/<model("nthub_constructions.nthub_constructions"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('nthub_constructions.object', {
#             'object': obj
#         })
