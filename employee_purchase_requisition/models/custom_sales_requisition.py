from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CustomSalesRequisition(models.Model):
    _name = 'custom.sales.requisition'
    _description = 'Custom Sales Requisition'

    responsible_id = fields.Many2one('res.users', string='Responsible', required=True)
    requisition_date = fields.Date(string='Requisition Date', required=True)
    received_date = fields.Date(string='Received Date')
    requisition_deadline = fields.Date(string='Requisition Deadline', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True)
    order_type = fields.Selection([
        ('one_time', 'One-time Supply'),
        ('scheduled', 'Scheduled Supply')
    ], string='Type of Order', required=True)
    payment_method = fields.Selection([
        ('prepaid', 'Prepaid'),
        ('postpaid', 'Postpaid')
    ], string='Payment Method', required=True)
    supply_type = fields.Selection([
        ('single', 'Single Location'),
        ('multiple', 'Multiple Locations')
    ], string='Supply', required=True)
    required_delivery_date = fields.Date(string='Required Delivery Date')

    stage = fields.Selection([
        ('new', 'New'),
        ('cancel', 'Cancel'),
        ('sales_order_created', 'Sales Order Created'),
        ('updated', 'Requisition Was Updated'),
        ('requisition_sent', 'Requisition Was Sent')
    ], string='Stage', default='new')

    sales_requisition_order_ids = fields.One2many(
        'custom.sales.requisition.order',  # Related model
        'requisition_id',  # The Many2one field in the related model
        string='Sales Requisition Orders'
    )

    # Picking Details Fields
    source_location_id = fields.Many2one('stock.location', string='Source Location')
    destination_location_id = fields.Many2one('stock.location', string='Destination Location')
    delivery_to_id = fields.Many2one('stock.picking.type', string='Delivery To')
    internal_picking_id = fields.Many2one('stock.picking.type', string='Internal Picking')

    # Related field to get the address from the destination_location_id
    address = fields.Char(related='destination_location_id.address', string='Destination Address', readonly=True)

    # Method to submit the offer and update relevant purchase requisition order lines


    def action_submit_offer(self):
        for order in self.sales_requisition_order_ids:
            # Search for the matching purchase requisition order lines based on the unique_id
            purchase_order_line = self.env['custom.purchase.requisition.order'].search([
                ('unique_id', '=', order.unique_id),
                ('requisition_id', '!=', False)
            ], limit=1)

            # Update the purchase requisition order line's unit_price
            if purchase_order_line:
                purchase_order_line.unit_price = order.unit_price

        # Update the stage after submitting the offer
        self.stage = 'requisition_sent'
class CustomSalesRequisitionOrder(models.Model):
    _name = 'custom.sales.requisition.order'
    _description = 'Custom Sales Requisition Order'

    requisition_id = fields.Many2one('custom.sales.requisition', string='Requisition Reference')
    product_category_id = fields.Many2one('product.category', string='Product Category', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True,
                                 domain="[('categ_id', '=', product_category_id)]")
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', required=True)
    location_id = fields.Many2one('stock.location', string='Location')

    # Add a related field to get the address from the location_id
    address = fields.Char(related='location_id.address', string='Destination Address', readonly=True)

    # Related field to get the value of supply_type from the parent requisition
    supply_type = fields.Selection(related='requisition_id.supply_type', string="Supply Type", store=True)

    # Unit price comes from sales requisition, and is readonly in purchase requisition
    unit_price = fields.Float(string='Unit Price')

    # Computed field for total (unit_price * quantity)
    total = fields.Float(string='Total', compute='_compute_total', store=True)

    # Unique identifier field to link with Purchase Requisition
    unique_id = fields.Char(string='Unique Identifier')

    @api.depends('unit_price', 'quantity')
    def _compute_total(self):
        for line in self:
            line.total = line.unit_price * line.quantity

    @api.onchange('location_id')
    def _onchange_location_id(self):
        # Check if supply_type is 'single' and location_id is set
        if self.supply_type == 'single' and self.location_id:
            raise ValidationError(
                "You cannot set a location for a 'Single Location' supply type. Please choose 'Multiple Locations' if you want to assign locations."
            )
