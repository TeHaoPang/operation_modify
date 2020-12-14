from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

class ChangeProductionQtyInherit(models.TransientModel):
    _inherit = 'change.production.qty'

    """自訂一個detail 用來存放多來源原料明細"""
    change_production_qty_line_ids = fields.One2many('change.production.qty.line', 'change_production_qty_id')
    product_id = fields.Many2one('product.product', 'Product')
    location_dest_id = fields.Many2one('stock.location')

    """
    對原本change production qty物件內的deault_get()進行繼承動作 符合客製化需求
    改寫的內容，主要是增加多來源move line，可以取得一個預設值
    """
    @api.model
    def default_get(self, fields):
        res = super(ChangeProductionQtyInherit, self).default_get(fields)

        if 'mo_id' not in fields and not res.get('mo_id') and self._context.get('active_model') == 'mrp.production' and self._context.get('active_id'):
            res['mo_id'] = self._context['active_id']
        if 'product_qty' not in fields and not res.get('product_qty') and res.get('mo_id'):
            res['product_qty'] = self.env['mrp.production'].browse(res['mo_id']).product_qty
       
        move_id = self.env['mrp.production'].search([('id', '=', res['mo_id'])]).move_raw_ids.filtered(lambda x: x.product_id.product_tmpl_id.tracking == 'lot')
        res['product_id'] = move_id.product_id.id
        res['location_dest_id'] = move_id.location_dest_id.id

        """從move_id中取得原本製令的stock move line資料，放入新增的change_production_qty_line_ids中，讓使用者可以看到原本製令的原料來源位置"""
        lines = []
        for i in self.env['stock.move.line'].search([('move_id', '=', move_id.id), ('done_wo', '=', 'true')]):
            val = {
                'product_id': i.product_id.id,
                'lot_id': i.lot_id.id,
                'product_uom_qty': i.product_uom_qty,
                'product_uom_id': i.product_uom_id.id,
                'qty_done': i.qty_done,
                'location_id': i.location_id.id,
                'location_dest_id': i.location_dest_id.id,
                'move_id': move_id.id,
                'move_line_id': i.id
            }
            lines.append(val)
        res['change_production_qty_line_ids'] = [(0, 0, x) for x in lines]
        return res

    """
    approve按鈕功能改寫
    我先將多來源原料明細先做寫入change.prouduction.qty物件中，再去執行他原本按鈕的程式碼
    """
    @api.multi
    def change_prod_qty(self):
        print('多來源改寫')

        """請記得寫一個防呆去避免使用將同批號同產品且同位置的產品來源分成兩筆 ex:A產品 批號:1234 位置:Bed1 數量:10 把這東西分成兩筆數量分別5去進行多來源改動 by 龎學長"""

        """將使用者新增加的原料來源或修改的資料作新增、寫入進stock move line的動作"""
        for move_line in self.change_production_qty_line_ids:
            if len(move_line) == 0:
                break
            if move_line.move_id and move_line.move_line_id:
                '''
                再有開工單的情況下，會取得兩筆move line，
                一筆done_wo為true(實際的move_line)，另一筆(done_wo為false)為暫存move line(給工單使用的，之後會被unlink())
                '''
                temp = self.env['stock.move.line'].search([('move_id', '=', move_line.move_id.id),('location_id', '=', move_line.move_line_id.location_id.id),('lot_id', '=', move_line.move_line_id.lot_id.id)])
                """改寫現有move line"""
                for i in temp:
                    if i.done_wo is True:
                        i.update({
                            'lot_id': move_line.lot_id.id,
                            'location_id': move_line.location_id.id,
                            'product_uom_qty': move_line.product_uom_qty
                        })
                    else:
                        i.update({
                            'lot_id': move_line.lot_id.id,
                            'location_id': move_line.location_id.id,
                            'qty_done': move_line.product_uom_qty
                        })

            elif len(move_line.move_id) == 0:
                """沒有這筆move line 創新的"""
                self.env['stock.move.line'].create({
                    'move_id': self.change_production_qty_line_ids[0].move_id.id,
                    'name': self.mo_id.name,
                    'product_id': self.product_id.id,
                    'product_uom_qty': move_line.product_uom_qty,
                    'product_uom_id': self.product_id.product_tmpl_id.uom_id.id,
                    'lot_id': move_line.lot_id.id,
                    'location_id': move_line.location_id.id,
                    'location_dest_id': self.location_dest_id.id,
                    'workorder_id':self.change_production_qty_line_ids[0].move_id.workorder_id.id,
                    'picking_type_id': self.change_production_qty_line_ids[0].move_id.picking_type_id.id,
                    'group_id': self.change_production_qty_line_ids[0].move_id.group_id.id,
                    'production_id': self.mo_id.id
                })
                """更改stock quant中的預留數量(貌似直接使用create()去創造新的move_line並不會幫你改動stock quant的預留數量，可能是我不夠強，找不到)"""
                quant = self.env['stock.quant'].search([('product_id', '=', move_line.product_id.id),
                                                        ('location_id', '=', move_line.location_id.id),
                                                        ('lot_id', '=', move_line.lot_id.id)])
                quant.write({'reserved_quantity': quant.reserved_quantity+move_line.product_uom_qty})

                """進入該筆製令的工單來新增其active_move_line"""
                wo = self.env['mrp.workorder'].search([('production_id', '=', self.mo_id.id)])
                if wo:
                    wo.active_move_line_ids.create({
                        'move_id': self.change_production_qty_line_ids[0].move_id.id,
                        'name': self.mo_id.name,
                        'product_id': self.product_id.id,
                        'product_uom_id': self.product_id.product_tmpl_id.uom_id.id,
                        'qty_done': move_line.product_uom_qty,
                        'lot_id': move_line.lot_id.id,
                        'location_id': move_line.location_id.id,
                        'location_dest_id': self.location_dest_id.id,
                        'picking_type_id': self.change_production_qty_line_ids[0].move_id.picking_type_id.id,
                        'group_id': self.change_production_qty_line_ids[0].move_id.group_id.id,
                        'production_id': self.mo_id.id,
                        'workorder_id': self.change_production_qty_line_ids[0].move_id.workorder_id.id,
                        'done_wo': False,
                    })
        res = super(ChangeProductionQtyInherit, self).change_prod_qty()
        return res

class ChangeProductionQtyLine(models.TransientModel):
    _name = 'change.production.qty.line'

    change_production_qty_id = fields.Many2one('change.production.qty')
    product_id = fields.Many2one('product.product', 'Product')
    lot_id = fields.Many2one('stock.production.lot', 'Lot/Serial Number')
    product_uom_qty = fields.Float('To Consume', digits=dp.get_precision('Product Unit of Measure'))
    product_uom_id = fields.Many2one('uom.uom', 'Unit of Measure')
    qty_done = fields.Float('Consumed', digits=dp.get_precision('Product Unit of Measure'))
    location_id = fields.Many2one('stock.location')
    location_dest_id = fields.Many2one('stock.location')
    move_id = fields.Many2one('stock.move')
    move_line_id = fields.Many2one('stock.move.line')


class StockMoveMethodModify(models.Model):
    _inherit = "stock.move"
    "改寫_decrease_reserved_quanity()"
    def _decrease_reserved_quanity(self, quantity):
        move_line_to_unlink = self.env['stock.move.line']
        check_move_line = self.env['stock.move.line'].search([('move_id', '=', self.id)])
        """加這一行而已"""
        if len(check_move_line) > 1:
            return True
        """加這一行而已"""
        for move in self:
            reserved_quantity = quantity
            
            for move_line in self.move_line_ids:
                if move_line.product_uom_qty > reserved_quantity:
                    move_line.product_uom_qty = reserved_quantity
                else:
                    move_line.product_uom_qty = 0
                    reserved_quantity -= move_line.product_uom_qty
                if not move_line.product_uom_qty and not move_line.qty_done:
                    move_line_to_unlink |= move_line
        move_line_to_unlink.unlink()
        return True
class MrpWorkorderEdit(models.Model):
    _inherit = 'mrp.workorder'

    """override _generate_lot_ids()"""
    def _generate_lot_ids(self):
        self.ensure_one()
        MoveLine = self.env['stock.move.line']
        tracked_moves = self.move_line_ids.filtered(
            lambda move: move.state not in ('done', 'cancel') and move.product_id.tracking != 'none' and move.product_id != self.production_id.product_id and move.move_id.bom_line_id)
        for move in tracked_moves:
            qty = move.move_id.unit_factor * self.qty_producing
            if move.product_id.tracking == 'serial':
                while float_compare(qty, 0.0, precision_rounding=move.move_id.product_uom.rounding) > 0:
                    MoveLine.create({
                        'move_id': move.move_id.id,
                        'product_uom_qty': 0,
                        'product_uom_id': move.move_id.product_uom.id,
                        'qty_done': min(1, qty),
                        'production_id': self.production_id.id,
                        'lot_id': move.lot_id.id,
                        'workorder_id': self.id,
                        'product_id': move.product_id.id,
                        'done_wo': False,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                    })
                    qty -= 1
            else:
                MoveLine.create({
                    'move_id': move.move_id.id,
                    'product_uom_qty': 0,
                    'product_uom_id': move.move_id.product_uom.id,
                    'qty_done': move.product_uom_qty,
                    'product_id': move.product_id.id,
                    'production_id': self.production_id.id,
                    'lot_id': move.lot_id.id,
                    'workorder_id': self.id,
                    'done_wo': False,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                })

    """
    依據多來源原料位置，同步生成多目的地製成品
    """
    @api.multi
    def record_production(self):
        res = super(MrpWorkorderEdit, self).record_production()


        source_product = self.env['mrp.bom.line'].search([('bom_id', '=', self.production_id.bom_id.id)]).filtered(lambda x: x.product_id.product_tmpl_id.tracking == 'lot').product_id

        source_move_lines = self.move_line_ids.filtered(lambda x: x.product_id.id == source_product.id)

        finished_move_lines = self.move_line_ids.filtered(lambda x: x.product_id.id == self.product_id.id)
        finish_move_id = finished_move_lines[0].move_id.id
       
        print(self.env['stock.move.line'].search([('move_id', '=', finish_move_id)]))
        count=0
        for temp in source_move_lines:
            if count == 0:
                print(finished_move_lines)
                finished_move_lines.update({
                    'product_uom_qty': temp.product_uom_qty,
                    'qty_done': temp.qty_done,
                    'location_id': temp.location_dest_id.id,
                    'location_dest_id': temp.location_id.id,
                    # 'lot_id': finished_move_lines.lot_id.id,
                })
               
                count += 1
            else:
                test=self.env['stock.move.line'].create({
                    'move_id': finish_move_id,
                    'product_id': self.product_id.id,
                    'product_uom_id': temp.product_uom_id.id,
                    'product_uom_qty': temp.product_uom_qty,
                    'qty_done': temp.qty_done,
                    'lot_id': finished_move_lines.lot_id.id,
                    'location_id': temp.location_dest_id.id,
                    'location_dest_id': temp.location_id.id,
                    'state': 'assigned',
                    'reference': temp.reference,
                    'workorder_id': self.id,
                    # 'done_wo': True,
                    # 'done_move': False
                })
               
        return True
