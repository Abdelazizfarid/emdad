# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Ashok PK (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from datetime import date
from email.policy import default

from odoo import fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Datetime
from odoo.tools.safe_eval import datetime


class PurchaseOrder(models.Model):
    """Class to add new field in purchase order"""

    _inherit = 'purchase.order'

    requisition_order = fields.Char(
        string='Requisition Order',
        help='Set a requisition Order')

    location_type = fields.Selection(string='Location Type', selection=[('single_location', 'Single Location'),
                                                                        ('multi_locations', 'Multi Locations')])
    location_id = fields.Many2one('stock.location', string='Vendor Location', domain=[('usage', '=', 'internal')])
    state = fields.Selection(selection_add=[
        ('close', 'Close'),
        ('expired', 'Expired'),
        ('rejected', 'Rejected')
    ], ondelete={'close': 'set default'})

    quotation_deadline = fields.Date(string='Deadline Date')
    related_sale_order_id = fields.Many2one('sale.order', string='Related Sale Order')

    def button_revise(self):
        related_sale_orders = self.env['sale.order'].search([
            ('related_purchase_requisition_id', '=', self.related_purchase_requisition_id.id),
        ])
        if related_sale_orders:
            related_sale_orders.state = 'price_revise'

    def button_reextend(self):
        related_sale_orders = self.env['sale.order'].search([
            ('related_purchase_requisition_id', '=', self.related_purchase_requisition_id.id),
        ])
        if related_sale_orders:
            related_sale_orders.state = 'deadline_reextend'

    def button_reject(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Purchase Order',
            'res_model': 'purchase.order.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': self.ids,
            },
        }

    def button_confirm(self):
        current_day = date.today()
        for order in self:
            if order.quotation_deadline and order.quotation_deadline < current_day:
                # Update the state to 'expired' and need_revise to True
                order.sudo().write({
                    'state': 'expired',
                })
                order.message_post(
                    body=f"This order is expired click button need revise to renewal."
                )
            else:
                # Proceed with the normal confirmation logic
                res = super(PurchaseOrder, self).button_confirm()

                if order.related_purchase_requisition_id:
                    # Get all related purchase orders except the current one
                    related_orders = self.env['purchase.order'].search([
                        ('related_purchase_requisition_id', '=', order.related_purchase_requisition_id.id),
                        ('id', '!=', order.id),  # Exclude the current order
                        ('state', 'not in', ['cancel', 'close'])  # Exclude cancelled or already closed orders
                    ])
                    if related_orders:
                        for record in related_orders:
                            record.write({'state': 'close'})
                            record.message_post(
                                body=f"Order closed because a related purchase order was confirmed."
                            )
                if order.related_sale_order_id:
                    order.related_sale_order_id.sudo().write({
                        'state': 'purchase_approved'
                    })

                return res




class PurchaseOrderLines(models.Model):
    """Class to add new field in purchase order"""

    _inherit = 'purchase.order.line'

    location_id = fields.Many2one('stock.location', string='Vendor Location', domain=[('usage', '=', 'internal')])



class PurchaseOrderRejectWizard(models.TransientModel):
    _name = 'purchase.order.reject.wizard'
    _description = 'Purchase Order Reject Wizard'

    rejection_reason = fields.Text(string="Rejection Reason", required=True)

    def action_reject(self):
        active_ids = self.env.context.get('active_ids', [])
        purchase_orders = self.env['purchase.order'].browse(active_ids)
        for order in purchase_orders:
            order.state = 'rejected'
            order.message_post(
                body=f"Purchase Order Rejected. Reason: {self.rejection_reason}"
            )

class PurchaseOrderConfirmWizard(models.TransientModel):
    _name = 'purchase.order.confirm.wizard'
    _description = 'Purchase Order Confirm Wizard'

    message = fields.Text(
        default="Are you sure you want to confirm this Purchase Order?",
        readonly=True
    )

    def action_confirm(self):
        # Confirm the purchase order
        active_id = self.env.context.get('active_id')
        if active_id:
            order = self.env['purchase.order'].browse(active_id)
            order.with_context(skip_confirmation=True).button_confirm()
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        # Cancel the confirmation and close the wizard
        return {'type': 'ir.actions.act_window_close'}

