# -*- coding: utf-8 -*-
from odoo import http

# class OperationModify(http.Controller):
#     @http.route('/operation_modify/operation_modify/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/operation_modify/operation_modify/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('operation_modify.listing', {
#             'root': '/operation_modify/operation_modify',
#             'objects': http.request.env['operation_modify.operation_modify'].search([]),
#         })

#     @http.route('/operation_modify/operation_modify/objects/<model("operation_modify.operation_modify"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('operation_modify.object', {
#             'object': obj
#         })