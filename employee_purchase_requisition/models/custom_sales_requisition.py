from odoo import models, fields, api,_
from odoo.exceptions import ValidationError
from odoo.tools import ormcache


class CustomSalesRequisition(models.Model):
    _name = 'custom.sales.requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Custom Sales Requisition'

    active = fields.Boolean(default=True)
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
    prepaid_date = fields.Date(string='Prepaid')

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
    total_before_tax = fields.Float(string="Total Before Tax", compute="_compute_totals", store=True)
    tax = fields.Float(string="Tax", compute="_compute_totals", store=True)
    total = fields.Float(string="Total", compute="_compute_totals", store=True)
    notes = fields.Html(string="Notes",readonly=True)
    is_service = fields.Boolean("Is Service")
    unique_id = fields.Char()
    related_purchase_requisition_id = fields.Many2one('custom.purchase.requisition', "Related Requisition")
    @api.depends('sales_requisition_order_ids.total', 'sales_requisition_order_ids.unit_price', 'sales_requisition_order_ids.tax_id')
    def _compute_totals(self):
        for requisition in self:
            total_before_tax = 0
            total_tax = 0
            total_amount = 0
            for line in requisition.sales_requisition_order_ids:
                subtotal = line.unit_price * line.quantity
                total_before_tax += subtotal
                if line.tax_id:
                    tax_amount = line.tax_id.amount / 100 * subtotal
                    total_tax += tax_amount
            total_amount = total_before_tax + total_tax
            requisition.total_before_tax = total_before_tax
            requisition.tax = total_tax
            requisition.total = total_amount

    def action_submit_offer(self):
        if not self.is_service:
            self.env['purchase.order'].create({
                'partner_id':self.company_id.id,
                'related_purchase_requisition_id':self.related_purchase_requisition_id.id,
                'order_line': [(0, 0, {
                'product_id': order.product_id.id,
                'product_qty': order.quantity,
                'price_unit': order.unit_price,
                'product_uom': order.uom_id.id or order.product_id.uom_id.id,
                'name': order.description or '',
                'date_planned': fields.Date.today(),
                'taxes_id': [(6, 0, [order.tax_id.id])] if order.tax_id else [(5,)],
            })for order in self.sales_requisition_order_ids]
            })

        else:
            for rec in self:
                purchase_order = self.env['custom.purchase.requisition'].search([
                    ('unique_id', '=', rec.unique_id)
                ], limit=1)

                if purchase_order:
                    for line_sale in rec.sales_requisition_order_ids:
                        # Create a new line for each sale line in the purchase requisition order
                        self.env['custom.purchase.requisition.order'].create({
                            'vendor_product_id': line_sale.vendor_product_id.id,
                            'uom_id': line_sale.uom_id.id,
                            'description': line_sale.description,
                            'quantity': line_sale.quantity,
                            'unit_price': line_sale.unit_price,
                            'total': line_sale.total,
                            'tax_id': line_sale.tax_id.id,
                            'vendor_id': rec.company_id.id,
                            'requisition_id': purchase_order.id  # Link to the current purchase order
                        })

        self.stage = 'requisition_sent'
class CustomSalesRequisitionOrder(models.Model):
    _name = 'custom.sales.requisition.order'
    _description = 'Custom Sales Requisition Order'

    requisition_id = fields.Many2one('custom.sales.requisition', string='Requisition Reference')
    product_category_id = fields.Many2one('product.category', string='Product Category')
    product_id = fields.Many2one('product.product', string='Customer Product',
                                 domain="[('categ_id', '=', product_category_id)]")
    suggestion_product_id = fields.Many2one('product.product', string='Suggestion Product')
    vendor_product_id = fields.Many2one('product.product', string=' Vendor Product')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)

    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', required=True)
    location_id = fields.Many2one('stock.location', string='Vendor Location')
    customer_location_id = fields.Many2one('stock.location', string='Customer Location',readonly=True)

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
    vendor_id = fields.Many2one('res.company', string="Vendor")
    deadline = fields.Date(string='Deadline Date')

    @api.depends('unit_price', 'quantity', 'tax_id')
    def _compute_total(self):
        for line in self:
            subtotal = line.unit_price * line.quantity
            tax_amount = 0
            if line.tax_id:
                tax_amount = line.tax_id.amount / 100 * subtotal  # Compute tax based on tax percentage
            line.total = subtotal + tax_amount

    @api.onchange('location_id')
    def _onchange_location_id(self):
        # Check if supply_type is 'single' and location_id is set
        if self.supply_type == 'single' and self.location_id:
            raise ValidationError(
                "You cannot set a location for a 'Single Location' supply type. Please choose 'Multiple Locations' if you want to assign locations."
            )

    def address_icon(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info' if self.location_id else 'danger',
                'title': _("Destination Address") if self.location_id else _(""),
                'message': f"{self.location_id.address}" if self.location_id else "No Location Chosen",
                'next': {
                    'type': 'ir.actions.act_window_close'
                },
            }
        }

    def copy_product(self):
        product_obj = self.env['product.product'].browse(self.product_id.id)
        copied_product = product_obj.sudo().copy({
            'company_id':self.requisition_id.company_id.id,'name':self.product_id.name
        })
        return copied_product

class ReceivingDate(models.Model):
    _name = 'sales.receiving.date'
    _description = 'Receiving Date'

    unique_id = fields.Char(string='Unique Identifier')
    receiving_date = fields.Date(string='Receiving Date', required=True)
    requisition_id = fields.Many2one('custom.sales.requisition', string='Requisition Reference', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity = fields.Float(string='Quantity')
    location_id = fields.Many2one('stock.location', string='Location')
    vendor_id = fields.Many2one('res.company', string='Vendors')

