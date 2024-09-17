import uuid

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CustomPurchaseRequisition(models.Model):
    _name = 'custom.purchase.requisition'
    _description = 'Custom Purchase Requisition'
    responsible_id = fields.Many2one('res.users', string='Responsible',default=lambda self: self.env.user.id)
    requisition_date = fields.Date(string='Requisition Date', required=True,default=fields.Date.today)
    received_date = fields.Date(string='Receiving Date')
    requisition_deadline = fields.Date(string='Requisition Deadline', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,default=lambda self: self.env.company.id)
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
    ], string='Prepaid',)
    payment_term = fields.Selection([
        ('op_30', '30 days'),
        ('op_60', '60 days'),
        ('op_90', '90 days'),
        ('op_120', '120 days')
    ], string='Payment Terms', )
    supplier_type = fields.Selection(
        [('single', 'Single'), ('multiple', 'Multiple')],
        string="Supplier Type",
        required=True,  # Make the field required
        default='single'  # Set the default value
    )
    single_location_id = fields.Many2one('stock.location', string='Location',domain=[('usage', '=', 'internal')])


    products_category_type = fields.Selection(
        [('single', 'Single'), ('multiple', 'Multiple')],
        string="Category Type",
        required=True,  # Make the field required
        default='single'  # Set the default value
    )
    single_category_id = fields.Many2one('product.category', string='Product Category')


    supply_type = fields.Selection(
        [('single', 'Single Location'), ('multiple', 'Multiple Locations')],
        string="Supply Type",
        required=True,  # Make the field required
        default='single'  # Set the default value
    )
    single_vendor_id = fields.Many2one('res.company', string='Vendor',)

    stage = fields.Selection([
        ('new', 'New'),
        ('cancel', 'Cancel'),
        ('purchase_order_created', 'Purchase Order Created'),
        ('received', 'Received'),
        ('requisition_sent', 'Requisition Was Sent')
    ], string='Stage', default='new')

    requisition_order_ids = fields.One2many(
        'custom.purchase.requisition.order',  # Related model
        'requisition_id',  # The Many2one field in the related model
        string='Requisition Orders'
    )
    receiving_order_ids = fields.One2many(
        'receiving.date',  # Related model
        'requisition_id',  # The Many2one field in the related model
        string='Receiving Date'
    )

    # Picking Details Fields
    source_location_id = fields.Many2one('stock.location', string='Source Location',default=lambda self: self.env.user.assigned_location.id)
    destination_location_id = fields.Many2one('stock.location', string='Destination Location',domain=[('usage', '=', 'internal')])
    delivery_to_id = fields.Many2one('stock.picking.type', string='Delivery To')
    internal_picking_id = fields.Many2one('stock.picking.type', string='Internal Picking')
    # Add a related field to get the address from the destination_location_id
    address = fields.Char(related='destination_location_id.address', string='Destination Address', readonly=True)
    # New computed field to display vendor offers
    vendors_offers = fields.Text(string='Vendors Offers', compute='_compute_vendors_offers')
    # Chosen vendor field
    vendor_ids = fields.Many2many('res.company', string='Vendors', compute='_compute_vendor_ids')
    chosen_vendor_id = fields.Many2one('res.company', string='Chosen Vendor', domain="[('id', 'in', vendor_ids)]")
    total_before_tax = fields.Float(string="Total Before Tax", compute="_compute_totals", store=True)
    tax = fields.Float(string="Tax", compute="_compute_totals", store=True)
    total = fields.Float(string="Total", compute="_compute_totals", store=True)

    # @api.onchange('products_category_type', 'single_category_id', 'requisition_order_ids')
    # def _onchange_products_category_type(self):
    #     """
    #     Onchange to filter the product_id domain in requisition_order_ids based on products_category_type.
    #     """
    #     domain = {}
    #     if self.products_category_type == 'single':
    #         # Filter product_id by single_category_id for single category type
    #         if self.single_category_id:
    #             for order in self.requisition_order_ids:
    #                 domain['product_id'] = [('categ_id', '=', self.single_category_id.id)]
    #                 order.product_id = False  # Clear product selection when category changes
    #     else:
    #         # Filter product_id by product_category_id in each requisition order for multiple category type
    #         for order in self.requisition_order_ids:
    #             if order.product_category_id:
    #                 domain['product_id'] = [('categ_id', '=', order.product_category_id.id)]
    #             else:
    #                 domain['product_id'] = []
    #             order.product_id = False  # Clear product selection when category changes
    #
    #     return {'domain': domain}

    @api.depends('requisition_order_ids.total', 'requisition_order_ids.unit_price', 'requisition_order_ids.tax_id')
    def _compute_totals(self):
        for requisition in self:
            total_before_tax = 0
            total_tax = 0
            total_amount = 0
            for line in requisition.requisition_order_ids:
                subtotal = line.unit_price * line.quantity
                total_before_tax += subtotal
                if line.tax_id:
                    tax_amount = line.tax_id.amount / 100 * subtotal
                    total_tax += tax_amount
            total_amount = total_before_tax + total_tax
            requisition.total_before_tax = total_before_tax
            requisition.tax = total_tax
            requisition.total = total_amount

    # Compute vendor_ids from requisition_order_ids
    @api.depends('requisition_order_ids')
    def _compute_vendor_ids(self):
        for record in self:
            record.vendor_ids = record.requisition_order_ids.mapped('vendor_id').ids  # Store only IDs
            print(record.vendor_ids)


    @api.depends('requisition_order_ids')
    def _compute_vendors_offers(self):
        for record in self:
            offers = []
            vendor_totals = {}

            # Loop through requisition_order_ids and sum totals per vendor
            for line in record.requisition_order_ids:
                if line.vendor_id:
                    if line.vendor_id not in vendor_totals:
                        vendor_totals[line.vendor_id] = 0
                    vendor_totals[line.vendor_id] += line.total  # Assuming `total` is the price of the line

            # Format the offers string
            for vendor, total in vendor_totals.items():
                offers.append(f"{vendor.name}: {total} EGP")

            # Join offers for display
            record.vendors_offers = "\n".join(offers)

    @api.model
    def create(self, vals):
        # Call super to create the record first
        requisition = super(CustomPurchaseRequisition, self).create(vals)

        # Validate supply_type
        if requisition.supply_type == 'single':
            if not requisition.single_location_id:
                raise ValidationError("Location must be specified for single supply type.")
        else:
            for line in requisition.requisition_order_ids:
                if not line.location_id:
                    raise ValidationError("Each requisition line must have a location specified for this supply type.")

        # Validate products_category_type
        if requisition.products_category_type == 'single':
            if not requisition.single_category_id:
                raise ValidationError("Product Category must be specified for single category type.")
        else:
            for line in requisition.requisition_order_ids:
                if not line.product_category_id:
                    raise ValidationError(
                        "Each requisition line must have a product category specified for this category type.")

        # Validate vendor for supply_type
        if requisition.supply_type == 'single':
            if not requisition.single_vendor_id:
                raise ValidationError("Vendor must be specified for single supply type.")
        else:
            for line in requisition.requisition_order_ids:
                if not line.vendor_id:
                    raise ValidationError("Each requisition line must have a vendor specified for this supply type.")

        return requisition

    def write(self, vals):
        # Call super to update the record first
        result = super(CustomPurchaseRequisition, self).write(vals)

        for requisition in self:
            # Validate supply_type
            if requisition.supply_type == 'single':
                if not requisition.single_location_id:
                    raise ValidationError("Location must be specified for single supply type.")
            else:
                for line in requisition.requisition_order_ids:
                    if not line.location_id:
                        raise ValidationError(
                            "Each requisition line must have a location specified for this supply type.")

            # Validate products_category_type
            if requisition.products_category_type == 'single':
                if not requisition.single_category_id:
                    raise ValidationError("Product Category must be specified for single category type.")
            else:
                for line in requisition.requisition_order_ids:
                    if not line.product_category_id:
                        raise ValidationError(
                            "Each requisition line must have a product category specified for this category type.")

            # Validate vendor for supply_type
            if requisition.supply_type == 'single':
                if not requisition.single_vendor_id:
                    raise ValidationError("Vendor must be specified for single supply type.")
            else:
                for line in requisition.requisition_order_ids:
                    if not line.vendor_id:
                        raise ValidationError(
                            "Each requisition line must have a vendor specified for this supply type.")

        return result

    # Method to create sales requisitions for vendors
    def action_submit_requisition(self):
        # Find unique vendors in the requisition_order_ids
        vendors = list(set(self.requisition_order_ids.mapped('vendor_id')))
        for vendor in vendors:
            # Create the sales requisition for each vendor
            sales_requisition = self.env['custom.sales.requisition'].create({
                'responsible_id': self.responsible_id.id,
                'requisition_date': self.requisition_date,
                'requisition_deadline': self.requisition_deadline,
                'company_id': vendor.id,  # Vendor is the company here
                'order_type': self.order_type,
                'payment_method': self.payment_method,
                'supply_type': self.supply_type,
                'required_delivery_date': self.required_delivery_date,
                'source_location_id': self.source_location_id.id if self.source_location_id else False,  # Pass the ID
                'destination_location_id': self.destination_location_id.id if self.destination_location_id else False,
                # Pass the ID
                'delivery_to_id': self.delivery_to_id.id if self.delivery_to_id else False,  # Pass the ID
                'internal_picking_id': self.internal_picking_id.id if self.internal_picking_id else False,
                # Pass the ID
            })

            # Create the sales requisition order lines for the vendor
            for order in self.requisition_order_ids.filtered(lambda o: o.vendor_id == vendor):
                # Generate a unique identifier for mapping
                unique_id = str(uuid.uuid4())  # Using UUID for unique ID generation

                # Set the unique_id in the purchase requisition order line
                order.write({'unique_id': unique_id})

                self.env['custom.sales.requisition.order'].create({
                    'requisition_id': sales_requisition.id,
                    'product_category_id': order.product_category_id.id,
                    'product_id': order.product_id.id,
                    'uom_id': order.uom_id.id,
                    'description': order.description,
                    'quantity': order.quantity,
                    'location_id': order.location_id.id if order.location_id else False,  # Pass the ID
                    'unique_id': unique_id,
                })

        # Update stage after submission
        self.stage = 'requisition_sent'

    def action_approve_offer(self):
        if not self.chosen_vendor_id:
            raise ValidationError("Please select a vendor to approve the offer.")

        # Create a purchase order for the chosen vendor
        purchase_order = self.env['purchase.order'].sudo().create({
            'partner_id':  self.chosen_vendor_id.partner_id.id,
            'company_id': self.company_id.id,
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'product_qty': line.quantity,
                'price_unit': line.unit_price,
                'date_planned': fields.Datetime.now(),
                'name': line.description or '',
                'product_uom': line.uom_id.id,
            }) for line in self.requisition_order_ids if line.vendor_id == self.chosen_vendor_id],
        })

        # Create a sales order for the chosen vendor's company
        self.env['sale.order'].sudo().create({
            'partner_id': self.company_id.partner_id.id,  # The current company will be the customer
            'company_id': self.chosen_vendor_id.id,  # The chosen vendor will be the selling company
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'price_unit': line.unit_price,
                'name': line.description or '',
                'product_uom': line.uom_id.id,
            }) for line in self.requisition_order_ids if line.vendor_id == self.chosen_vendor_id],
        })

        # Update the stage to indicate the offer is approved
        self.stage = 'purchase_order_created'

        return {
            'name': 'Purchase Order',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': purchase_order.id,
        }


class CustomPurchaseRequisitionOrder(models.Model):
    _name = 'custom.purchase.requisition.order'
    _description = 'Custom Purchase Requisition Order'
    requisition_id = fields.Many2one('custom.purchase.requisition', string='Requisition Reference')
    product_category_id = fields.Many2one('product.category', string='Product Category')
    product_id = fields.Many2one('product.product', string='Product', required=True,)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', required=True)
    vendor_id = fields.Many2one('res.company', string='Vendor',)
    location_id = fields.Many2one('stock.location', string='Location',domain=[('usage', '=', 'internal')])
    # Add a related field to get the address from the destination_location_id
    address = fields.Char(related='location_id.address', string='Destination Address', readonly=True)

    # Add a related field to get the value of supply_type from the parent requisition
    supply_type = fields.Selection(related='requisition_id.supply_type', string="Supply Type", store=True)

    # Unit price comes from sales requisition, and is readonly in purchase requisition
    unit_price = fields.Float(string='Unit Price')
    tax_id = fields.Many2one('account.tax', string='Tax')


    # Computed field for total (unit_price * quantity)
    total = fields.Float(string='Total', compute='_compute_total', store=True)

    # Add unique identifier field to link with Sales Requisition
    unique_id = fields.Char(string='Unique Identifier')


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
class ReceivingDate(models.Model):
    _name = 'receiving.date'
    _description = 'Receiving Date'

    receiving_date = fields.Date(string='Receiving Date', required=True)
    requisition_id = fields.Many2one('custom.purchase.requisition', string='Requisition Reference', required=True)
