from odoo import models, fields, api, _

# class MutiMrpOrder(models.Model):
#     _name = 'muti.mrp.order'
#
#     name = fields.Char(string='名字', default=lambda x: _('New'))
#     mrp_ids = fields.One2many('mrp.production', 'muti_mrp_order_id')
#     product_id = fields.Many2one('product.product', 'Product')
#     bom_id = fields.Many2one('mrp.bom', 'Bill of Material')

# class MrpProductionEdit(models.Model):
#     _inherit = 'mrp.production'
#
#     muti_mrp_order_id = fields.Many2one('muti.mrp.order')
#     lot_id = fields.Many2one('stock.production.lot')

