from  odoo import models, fields

class PurchaseConfirmButtonInherit(models.Model):
    _inherit = 'purchase.order'


    def button_confirm(self):
        if not self.env.context.get('skip_confirmation'):
            return {
                'name': 'Confirm Purchase Order',
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order.confirm.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'active_id': self.id},
            }
        return super(PurchaseConfirmButtonInherit, self).button_confirm()