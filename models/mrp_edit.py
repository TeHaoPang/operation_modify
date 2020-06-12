from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.addons import decimal_precision as dp


class MrpEdit(models.TransientModel):
    _name = 'mrp.input'
    _description = '入庫生產單'
    """原製令資訊取得"""
    @api.model
    def default_get(self, fields):
        res = super(MrpEdit, self).default_get(fields)
        """取得製令產品id"""
        res['product_id'] = self.env['mrp.production'].search([('id', '=', self.env.context['active_id'])],
                                                              limit=1).product_id.id
        """取得製令id"""
        res['production_id'] = self.env.context.get('active_id')
        lines = []
        """取得move id"""
        temp = self.env['mrp.production'].search([('id', '=', self.env.context['active_id'])],
                                                 limit=1).move_raw_ids.filtered(lambda x: x.has_tracking == 'lot')
        """取得move line"""
        move_line = self.env['stock.move.line'].search([('move_id', '=', temp.id), ('done_wo', '=', True)])
        print(move_line)
        for i in move_line:
            val = {
                'product_id': i.product_id.id,
                'lot_id': i.lot_id.id,
                'qty_to_consume': i.product_uom_qty,
                'product_uom_id': i.product_uom_id.id,
                'qty_done': i.qty_done,
                'location_src_id': i.location_id.id,
                'location_dest_id': i.location_dest_id.id,
                'move_id': i.move_id.id,
            }
            lines.append(val)
        print(lines)
        """將多來源寫進入庫生產單明細中"""
        res['muti_input_source_line_ids'] = [(0, 0, x) for x in lines]

        # print(res['muti_input_source_line_ids'])
        print(res)
        return res

    production_id = fields.Many2one('mrp.production', 'Production')
    product_id = fields.Many2one('product.product', 'Product',)
    produce_qty = fields.Float(string='預先生產數量')
    muti_input_source_line_ids = fields.One2many('mrp.input.line', 'muti_input_id')

    """執行入庫function"""
    def mrp_edit2(self):
        origin_mo = self.env['mrp.production'].search([('id', '=', self.env.context['active_id'])])
        #print("開始測試")
        if origin_mo.product_qty < self.produce_qty:
            raise UserError('超過原生產單數量')
        if origin_mo.product_qty == self.produce_qty:
            raise UserError('生產數量無變動')
        qty_diff = origin_mo.product_qty - self.produce_qty
        #print(qty_diff)

        '''使用製令的update function 來更改原製令數量'''
        qty_wizard = self.env['change.production.qty'].create({
            'mo_id': origin_mo.id,
            'product_qty': qty_diff,
        })
        #print(qty_wizard)
        #print(qty_wizard.change_production_qty_line_ids)
        #print('123')
        move_line = self.muti_input_source_line_ids
        print(move_line)
        count = 0

        #print(qty_wizard.change_production_qty_line_ids[0].product_uom_qty)
        """請之後用雙重迴圈更改寫法"""
        """或者新增stock move line 的id來做比對"""
        for temp in qty_wizard.change_production_qty_line_ids:
            if move_line[count].lot_id.id == temp.lot_id.id and move_line[count].location_src_id.id == temp.location_id.id:
                temp.update({'product_uom_qty': temp.product_uom_qty-move_line[count].qty_to_do})
            count += 1
        #print(qty_wizard.change_production_qty_line_ids[0].product_uom_qty)
        #print(qty_wizard.change_production_qty_line_ids[1].product_uom_qty)

        qty_wizard.change_prod_qty()


        #print(origin_mo)
        """新增新的製令作為此入庫生產單的紀錄"""
        mo = self.env['mrp.production'].create({
            'product_id': origin_mo.product_id.id,
            'product_uom_id': origin_mo.product_uom_id.id,
            'product_qty': self.produce_qty,
            'bom_id': origin_mo.bom_id.id,
            'location_src_id': origin_mo.location_src_id.id,
            'location_dest_id': origin_mo.location_dest_id.id,
        })


        #print(mo)
        #print(mo.move_raw_ids)

        """新製令的檢查可用鈕"""
        mo.action_assign()
        #print(mo.move_raw_ids)

        move_id = mo.move_raw_ids.filtered(
            lambda x: x.has_tracking == 'lot' and x.product_id.id == move_line[0].product_id.id)
        print(move_id)
        print(move_id.active_move_line_ids)

        """將入庫生產單中的move line 填入新的製令中"""
        for new_move_line in move_line:
            if new_move_line.qty_to_do == 0:
                continue
            for temp in move_id.active_move_line_ids:
                if new_move_line.lot_id.id == temp.lot_id.id and new_move_line.location_src_id.id == temp.location_id.id:
                    print(temp)
                    temp.update({
                        'product_uom_qty': new_move_line.qty_to_do,
                    })
                else:
                    new = self.env['stock.move.line'].create({
                        'move_id': move_id.id,
                        'name': move_id.name,
                        'product_id': new_move_line.product_id.id,
                        # 'product_qty': new_move_line.qty_to_do,
                        'product_uom_qty': new_move_line.qty_to_do,
                        'product_uom_id': new_move_line.product_id.product_tmpl_id.uom_id.id,
                        'lot_id': new_move_line.lot_id.id,
                        'location_id': new_move_line.location_src_id.id,
                        'location_dest_id': new_move_line.location_dest_id.id,
                        'picking_type_id': move_id.picking_type_id.id,
                        'group_id': move_id.group_id.id,
                        'production_id': self.production_id.id
                    })
                    print(new)

                    """之後可能要判斷是否有預留"""
                    quant = self.env['stock.quant'].search([('product_id', '=', new_move_line.product_id.id),
                                                            ('location_id', '=', new_move_line.location_src_id.id),
                                                            ('lot_id', '=', new_move_line.lot_id.id)])
                    print(quant.reserved_quantity)
                    quant.write({'reserved_quantity': quant.reserved_quantity + new_move_line.qty_to_do})

        # print(mo.move_raw_ids[0].active_move_line_ids)
        # print(mo.move_raw_ids[1].active_move_line_ids)

        # # raise UserError("")
        #print('button_plan')
        """創建工單"""
        mo.button_plan()

        # print(mo.workorder_ids.active_move_line_ids[1].lot_id)
        # print(origin_mo.workorder_ids.active_move_line_ids[0].lot_id)
        final_lot = self.env['stock.production.lot'].search([('name', '=', mo.workorder_ids.active_move_line_ids[0].lot_id.name), ('product_id', '=', mo.workorder_ids.product_id.id)])
        if len(final_lot) == 1:
            mo.workorder_ids.write({'final_lot_id': final_lot.id})
        elif len(final_lot) == 0:
            new_lot = self.env['stock.production.lot'].create({
                'name': mo.workorder_ids.active_move_line_ids[0].lot_id.name,
                'product_id': mo.workorder_ids.product_id.id
            })
            mo.workorder_ids.write({'final_lot_id': new_lot.id})

        mo.workorder_ids.button_start()
        mo.workorder_ids.record_production()
        #print("test")
        return {'type': 'ir.actions.act_window_close'}

class MrpInputLine(models.TransientModel):
    _name = 'mrp.input.line'

    muti_input_id = fields.Many2one('mrp.input')
    product_id = fields.Many2one('product.product', 'Product')
    lot_id = fields.Many2one('stock.production.lot', 'Lot/Serial Number')
    qty_to_consume = fields.Float('To Consume', digits=dp.get_precision('Product Unit of Measure'))
    qty_to_do = fields.Float('預先製作', digits=dp.get_precision('Product Unit of Measure'))
    product_uom_id = fields.Many2one('uom.uom', 'Unit of Measure')
    qty_done = fields.Float('Consumed', digits=dp.get_precision('Product Unit of Measure'))
    location_src_id = fields.Many2one('stock.location')
    location_dest_id = fields.Many2one('stock.location')
    move_id = fields.Many2one('stock.move')

