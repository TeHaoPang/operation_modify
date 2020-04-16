from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

class ChangeProductionQtyInherit(models.TransientModel):
    _inherit = 'change.production.qty'

    change_production_qty_line_ids = fields.One2many('change.production.qty.line', 'change_production_qty_id')
    product_id = fields.Many2one('product.product', 'Product')
    location_dest_id = fields.Many2one('stock.location')

    @api.model
    def default_get(self, fields):
        res = super(ChangeProductionQtyInherit, self).default_get(fields)

        if 'mo_id' not in fields and not res.get('mo_id') and self._context.get('active_model') == 'mrp.production' and self._context.get('active_id'):
            res['mo_id'] = self._context['active_id']
        if 'product_qty' not in fields and not res.get('product_qty') and res.get('mo_id'):
            res['product_qty'] = self.env['mrp.production'].browse(res['mo_id']).product_qty
        print('change production qty default get')
        print(res)
        print(res['mo_id'])
        print(self.mo_id)
        print(self.env['mrp.production'].search([('id', '=', res['mo_id'])]).move_raw_ids)
        move_id = self.env['mrp.production'].search([('id', '=', res['mo_id'])]).move_raw_ids.filtered(lambda x: x.product_id.product_tmpl_id.tracking == 'lot')
        res['product_id'] = move_id.product_id.id
        res['location_dest_id'] = move_id.location_dest_id.id
        print(move_id)

        lines = []
        for i in self.env['stock.move.line'].search([('move_id', '=', move_id.id), ('done_wo', '=', 'true')]):
            print(i)
            val = {
                'product_id': i.product_id.id,
                'lot_id': i.lot_id.id,
                'product_uom_qty': i.product_uom_qty,
                'product_uom_id': i.product_uom_id.id,
                'qty_done': i.qty_done,
                'location_id': i.location_id.id,
                'location_dest_id': i.location_dest_id.id,
                'move_id': move_id.id,
            }
            lines.append(val)
            print(lines)
        res['change_production_qty_line_ids'] = [(0, 0, x) for x in lines]
        print(res)
        return res

    @api.multi
    def change_prod_qty(self):

        res = super(ChangeProductionQtyInherit, self).change_prod_qty()
        print('多來源改寫')
        print(self.change_production_qty_line_ids)
        # print(self.change_production_qty_line_ids[0].product_uom_qty)
        # print(self.change_production_qty_line_ids[1].product_uom_qty)

        """請記得寫一個防呆去避免使用將同批號同產品且同位置的產品來源分成兩筆 ex:A產品 批號:1234 位置:Bed1 數量:10 把這東西分成兩筆數量分別5去進行多來源改動 by 龎學長"""

        for move_line in self.change_production_qty_line_ids:
            print(move_line.move_id)
            print(move_line)
            if len(move_line) == 0:
                break
            if move_line.move_id:
                print("測試二號")
                '''會取得兩筆'''
                temp = self.env['stock.move.line'].search([('move_id', '=', move_line.move_id.id),('location_id', '=', move_line.location_id.id),('lot_id', '=',move_line.lot_id.id)])
                print(temp)
                for i in temp:
                    if i.done_wo is True:
                        print('到這')
                        i.update({
                            'lot_id': move_line.lot_id.id,
                            'location_id': move_line.location_id.id,
                            # 'product_qty': move_line.product_uom_qty,
                            'product_uom_qty': move_line.product_uom_qty
                        })
                        quant = self.env['stock.quant'].search([('product_id', '=', move_line.product_id.id),
                                                        ('location_id', '=', move_line.location_id.id),
                                                        ('lot_id', '=', move_line.lot_id.id)])
                        print(quant)
                        print(quant.reserved_quantity)
                    else:
                        i.update({
                            'lot_id': move_line.lot_id.id,
                            'location_id': move_line.location_id.id,
                            'qty_done': move_line.product_uom_qty
                        })

            elif len(move_line.move_id) == 0:
                print('測試三號 沒有這筆move line 創新的')
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
                quant = self.env['stock.quant'].search([('product_id', '=', move_line.product_id.id),
                                                        ('location_id', '=', move_line.location_id.id),
                                                        ('lot_id', '=', move_line.lot_id.id)])
                print(quant.reserved_quantity)
                quant.write({'reserved_quantity': quant.reserved_quantity+move_line.product_uom_qty})

                print('test')
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
        print("結束")
        # res = super(ChangeProductionQtyInherit, self).change_prod_qty()

        # raise UserError('')
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


class StockMoveMethodModify(models.Model):
    _inherit = "stock.move"

    def _decrease_reserved_quanity(self, quantity):
        move_line_to_unlink = self.env['stock.move.line']
        check_move_line = self.env['stock.move.line'].search([('move_id', '=', self.id)])
        """加這一行而已"""
        if len(check_move_line) > 1:
            return True
        """加這一行而已"""
        for move in self:
            reserved_quantity = quantity
            # if len(self.move_line_ids) > 1:
            #     break
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

    """重新改寫_generate_lot_ids()"""
    def _generate_lot_ids(self):
        print('_generate_lot_ids')

        print(self.ensure_one())
        self.ensure_one()
        MoveLine = self.env['stock.move.line']
        tracked_moves = self.move_line_ids.filtered(
            lambda move: move.state not in ('done', 'cancel') and move.product_id.tracking != 'none' and move.product_id != self.production_id.product_id and move.move_id.bom_line_id)
        print(tracked_moves)
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
        print('結束')

    @api.multi
    def record_production(self):
        res = super(MrpWorkorderEdit, self).record_production()
        print("record_production 改寫")
        print(self.move_line_ids)

        source_product = self.env['mrp.bom.line'].search([('bom_id', '=', self.production_id.bom_id.id)]).filtered(lambda x: x.product_id.product_tmpl_id.tracking == 'lot')

        source_move_lines = self.move_line_ids.filtered(lambda x: x.product_id.id == source_product.id)
        print(source_move_lines)

        finished_move_lines = self.move_line_ids.filtered(lambda x: x.product_id.id == self.product_id.id)
        finish_move_id = finished_move_lines[0].move_id.id
        print(finish_move_id)
        print(finished_move_lines)
        print(finished_move_lines.state)

        print(self.final_lot_id.id)
        print(finished_move_lines.lot_id.id)

        print(self.env['stock.move.line'].search([('move_id', '=', finish_move_id)]))
        count=0
        for temp in source_move_lines:
            print(count)
            if count == 0:
                print(finished_move_lines)
                finished_move_lines.update({
                    'product_uom_qty': temp.product_uom_qty,
                    'qty_done': temp.qty_done,
                    'location_id': temp.location_dest_id.id,
                    'location_dest_id': temp.location_id.id,
                    # 'lot_id': finished_move_lines.lot_id.id,
                })
                print('上面')
                print(finished_move_lines)
                print(finished_move_lines.state)
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
                print('下面')
                print(test)

        print(self.env['stock.move.line'].search([('move_id', '=', finish_move_id)]))
        # raise UserError('')


        # raise UserError('')
        return True


