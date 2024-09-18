from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CustomSalesRequisition(models.Model):
    _name = 'custom.sales.requisition'
    _description = 'Custom Sales Requisition'

    responsible_id = fields.Many2one('res.users', string='Responsible', required=True, default=lambda self: self.env.user.id)
    requisition_date = fields.Date(string='Requisition Date', required=True, default=fields.Date.today)
    received_date = fields.Date(string='Received Date')
    requisition_deadline = fields.Date(string='Requisition Deadline', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company.id)

    order_type = fields.Selection([
        ('one_time', 'One-time Supply'),
        ('scheduled', 'Scheduled Supply')
    ], string='Type of Order', required=True)

    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('credit', 'Credit')
    ], string='Payment Method', required=True)

    prepaid = fields.Selection([
        ('op_30', '30 days'),
        ('op_60', '60 days'),
        ('op_90', '90 days'),
        ('op_120', '120 days')
    ], string='Prepaid')

    payment_term = fields.Selection([
        ('op_30', '30 days'),
        ('op_60', '60 days'),
        ('op_90', '90 days'),
        ('op_120', '120 days')
    ], string='Payment Terms')

    supplier_type = fields.Selection(
        [('single', 'Single'), ('multiple', 'Multiple')],
        string="Supplier Type",
        required=True,
        default='single'
    )

    products_category_type = fields.Selection(
        [('single', 'Single'), ('multiple', 'Multiple')],
        string="Category Type",
        required=True,
        default='single'
    )
    single_location_id = fields.Many2one('stock.location', string='Location', domain=[('usage', '=', 'internal')])
    single_category_id = fields.Many2one('product.category', string='Product Category')

    supply_type = fields.Selection([
        ('single', 'Single Location'),
        ('multiple', 'Multiple Locations')
    ], string='Supply', required=True, default='single')

    single_vendor_id = fields.Many2one('res.company', string='Vendor')

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

    receiving_order_ids = fields.One2many(
        'sales.receiving.date',  # Related model
        'requisition_id',  # The Many2one field in the related model
        string='Receiving Date'
    )

    # Picking Details Fields
    source_location_id = fields.Many2one('stock.location', string='Source Location', default=lambda self: self.env.user.assigned_location.id)
    destination_location_id = fields.Many2one('stock.location', string='Destination Location', domain=[('usage', '=', 'internal')])
    delivery_to_id = fields.Many2one('stock.picking.type', string='Delivery To')
    internal_picking_id = fields.Many2one('stock.picking.type', string='Internal Picking')

    # Related field to get the address from the destination_location_id
    address = fields.Char(related='destination_location_id.address', string='Destination Address', readonly=True)

    # Total Calculation Fields
    total_before_tax = fields.Float(string="Total Before Tax", store=True)
    tax = fields.Float(string="Tax", store=True)
    total = fields.Float(string="Total", store=True)


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
    product_category_id = fields.Many2one('product.category', string='Product Category')
    product_id = fields.Many2one('product.product', string='Product', required=True,
                                 domain="[('categ_id', '=', product_category_id)]")
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)
    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', required=True)
    location_id = fields.Many2one('stock.location', string='Location')

    # Add a related field to get the address from the location_id
    address = fields.Char(related='location_id.address', string='Destination Address', readonly=True)

    # Related field to get the value of supply_type from the parent requisition
    supply_type = fields.Selection(related='requisition_id.supply_type', string="Supply Type", store=True)

    # Unit price comes from sales requisition, and is readonly in purchase requisition
    unit_price = fields.Float(string='Unit Price')
    tax_id = fields.Many2one('account.tax', string='Tax')

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


class ReceivingDate(models.Model):
    _name = 'sales.receiving.date'
    _description = 'Receiving Date'

    unique_id = fields.Char(string='Unique Identifier')
    receiving_date = fields.Date(string='Receiving Date', required=True)
    requisition_id = fields.Many2one('custom.sales.requisition', string='Requisition Reference', required=True)
