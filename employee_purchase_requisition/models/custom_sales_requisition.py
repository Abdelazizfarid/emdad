from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CustomSalesRequisition(models.Model):
    _name = 'custom.sales.requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Custom Sales Requisition'

    active = fields.Boolean(default=True)
    responsible_id = fields.Many2one('res.users', string='Responsible', required=True,
                                     default=lambda self: self.env.user.id)
    requisition_date = fields.Date(string='Requisition Date', required=True, default=fields.Date.today)
    received_date = fields.Date(string='Received Date')
    requisition_deadline = fields.Date(string='Requisition Deadline', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company.id)
    customer_id = fields.Many2one('res.company', string='Customer', required=True)

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
        ('approved', 'Requisition Approved'),
        ('rejected', 'Rejected')
    ], string='Stage', default='new')

    sales_requisition_order_ids = fields.One2many(
        'custom.sales.requisition.order',  # Related model
        'requisition_id',  # The Many2one field in the related model
        string='Sales Requisition Orders'
    )
    suggestion_product_ids = fields.One2many(
        'product.suggest',  # Related model
        'suggest_id',  # The Many2one field in the related model
        string='Suggestion Products'
    )

    receiving_order_ids = fields.One2many(
        'sales.receiving.date',  # Related model
        'requisition_id',  # The Many2one field in the related model
        string='Receiving Date'
    )

    # Picking Details Fields
    source_location_id = fields.Many2one('stock.location', string='Source Location',
                                         default=lambda self: self.env.user.assigned_location.id)
    destination_location_id = fields.Many2one('stock.location', string='Destination Location',
                                              domain=[('usage', '=', 'internal')])
    delivery_to_id = fields.Many2one('stock.picking.type', string='Delivery To')
    internal_picking_id = fields.Many2one('stock.picking.type', string='Internal Picking')

    # Related field to get the address from the destination_location_id
    address = fields.Char(related='destination_location_id.address', string='Destination Address', readonly=True)

    # Tabs Boolean Field
    requisition_order_tab = fields.Boolean()
    receiving_order_order_tab = fields.Boolean()
    prepaid_tab = fields.Boolean()

    # Total Calculation Fields
    total_before_tax = fields.Float(string="Total Before Tax", compute="_compute_totals", store=True)
    tax = fields.Float(string="Tax", compute="_compute_totals", store=True)
    total = fields.Float(string="Total", compute="_compute_totals", store=True)
    notes = fields.Html(string="Notes", readonly=True)
    is_service = fields.Boolean("Is Service")
    unique_id = fields.Char()
    related_purchase_requisition_id = fields.Many2one('custom.purchase.requisition', "Related Requisition")

    @api.depends('sales_requisition_order_ids.total', 'sales_requisition_order_ids.unit_price',
                 'sales_requisition_order_ids.tax_id')
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

    def print_report(self):
        data = {
            'form': self.read()[0],
            'prepaid_date': self.prepaid_date,
            'requisition_date': self.requisition_date,
            'received_date': self.received_date,
            'requisition_deadline': self.requisition_deadline,
            'company_id': self.company_id.name,
            'order_type': self.order_type,
            'payment_method': self.payment_method,
            'prepaid': self.prepaid,
            'payment_term': self.payment_term,
            'supplier_type': self.supplier_type,
            'single_location_id': self.single_location_id.name,
            'products_category_type': self.products_category_type,
            'single_category_id': self.single_category_id.name,
            'supply_type': self.supply_type,
            'single_vendor_id': self.single_vendor_id.id,
            'stage': self.stage,
            'sales_requisition_order_ids': self.sales_requisition_order_ids.ids,
            'receiving_order_ids': self.receiving_order_ids.ids,
            'source_location_id': self.source_location_id.id,
            'destination_location_id': self.destination_location_id.id,
            'delivery_to_id': self.delivery_to_id.id,
            'internal_picking_id': self.internal_picking_id.id,
            'address': self.address,
            'responsible_id': self.responsible_id.name,
            'total_before_tax': self.total_before_tax,
            'tax': self.tax,
            'total': self.total,
            'notes': self.notes,
            'is_service': self.is_service,
            'requisition_order_tab': self.requisition_order_tab,
            'receiving_order_order_tab': self.receiving_order_order_tab,
            'prepaid_tab': self.prepaid_tab,
        }
        print(self.sales_requisition_order_ids.ids)
        return self.env.ref('employee_purchase_requisition.action_report_print_sales_requisition').report_action(
            self, data=data)

    def action_approve_requisition(self):
        # Check if any line in sales_requisition_order_ids does not have a vendor_product_id
        missing_products = self.sales_requisition_order_ids.filtered(lambda order: not order.vendor_product_id)
        if missing_products:
            raise ValidationError("You must choose your product for all sales requisition order lines before approving.")

        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.customer_id.partner_id.id,
            'company_id': self.company_id.id,
            'related_sale_requisition_id': self.id,
            'suggestion_product_ids': [(6, 0, self.suggestion_product_ids.ids)],  # Correctly linking Many2many
            'related_purchase_requisition_id': self.related_purchase_requisition_id.id,
            'unique_id': self.unique_id,
            'order_line': [(0, 0, {
                'customer_product_id': order.product_id.sudo().id,
                'product_id': order.vendor_product_id.sudo().id,
                'product_uom_qty': order.quantity,
                'price_unit': 0.0,
                'customer_name': order.description,
                'name': order.vendor_product_id.sudo().name,
            }) for order in self.sales_requisition_order_ids.sudo()],
        })
        self.stage = 'approved'

    def action_reject(self):
        self.stage = 'rejected'


class SaleOrderLines(models.Model):
    _inherit = 'sale.order.line'

    is_seen = fields.Boolean(string="Not Available")
    location_id = fields.Many2one('stock.location', string='Vendor Location', domain=[('usage', '=', 'internal')])
    customer_product_id = fields.Many2one('product.product', string='Customer Product')
    customer_name = fields.Char(string='Customer Description')

    def _create_procurement(self, product_qty, procurement_uom, values):
        """
        Override procurement creation to handle multi-location processing.
        """
        self.ensure_one()

        # Determine the location based on the order's location type
        if self.order_id.location_type == 'multi_locations':
            location = self.location_id
        else:
            location = self.order_id.location_id

        # Raise an error if no location is assigned
        if not location:
            raise ValidationError(
                f"No location specified for the sale order line of product: {self.product_id.display_name}."
            )

        # Create and return procurement with the determined location
        return self.env['procurement.group'].Procurement(
            self.product_id,
            product_qty,
            procurement_uom,
            location,
            self.product_id.display_name,
            self.order_id.name,
            self.order_id.company_id,
            values
        )


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    related_sale_requisition_id = fields.Many2one('custom.sales.requisition', "Related Requisition")
    related_purchase_requisition_id = fields.Many2one('custom.purchase.requisition', "Related Requisition")
    suggestion_product_ids = fields.One2many(
        'product.suggest',  # Related model
        'suggest_id',  # The Many2one field in the related model
        string='Suggestion Products'
    )
    quotation_deadline = fields.Date(string='Deadline Date')
    location_type = fields.Selection(string='Location Type', selection=[('single_location', 'Single Location'),
                                                                        ('multi_locations', 'Multi Locations')])
    location_id = fields.Many2one('stock.location', string='Vendor Location', domain=[('usage', '=', 'internal')])

    @api.onchange('location_type')
    def _onchange_location_type(self):
        for rec in self:
            rec.location_id = False
            if rec.order_line:
                for line in rec.order_line:
                    line.location_id = False

    unique_id = fields.Char()
    is_service = fields.Boolean("Is Service")
    state = fields.Selection(selection_add=[
        ('requisition_sent', 'Requisition Sent'),
        ('purchase_approved', 'Purchase Approved'),
        ('price_revise', 'Renew Prices'),
        ('deadline_reextend', 'Deadline Re Extend'),
    ], ondelete={'requisition_sent': 'set default'})

    def renew_prices(self):
        # Search for related purchase orders based on the related purchase requisition ID
        related_purchase_orders = self.env['purchase.order'].search([
            ('related_purchase_requisition_id', '=', self.related_purchase_requisition_id.id)
        ])

        if related_purchase_orders:
            for order in related_purchase_orders:
                # For each purchase order, loop through its order lines
                for line in order.order_line:
                    # Find the matching line in the current order (the order that is calling renew_prices)
                    matching_line = next((line for line in self.order_line if line.product_id.id == line.product_id.id),
                                         None)

                    if matching_line:
                        # Update the existing order line's price_unit and other fields
                        line.write({
                            'price_unit': matching_line.price_unit,  # Update the price_unit
                        })

                # Set the state of the purchase order to draft
                order.write({'state': 'draft'})

        # Update the state of the current object to 'requisition_sent'
        self.state = 'requisition_sent'

    def _can_be_confirmed(self):
        self.ensure_one()
        return self.state in {'draft', 'sent', 'purchase_approved'}

    def renew_deadline_date(self):
        related_purchase_orders = self.env['purchase.order'].search(
            [('related_purchase_requisition_id', '=', self.related_purchase_requisition_id.id)])
        if related_purchase_orders:
            for order in related_purchase_orders:
                order.write({'quotation_deadline': self.quotation_deadline,
                             'state': 'draft'})
        self.state = 'requisition_sent'

    def action_submit_offer(self):
        if not self.is_service:
            purchase_order = self.env['purchase.order'].sudo().create({
                'partner_id': self.company_id.partner_id.id,
                'related_sale_order_id': self.id,
                'company_id': self.related_purchase_requisition_id.company_id.id,
                'quotation_deadline': self.quotation_deadline,
                'location_type': self.location_type,
                'location_id': self.location_id.id if self.location_id else None,
                'related_purchase_requisition_id': self.related_purchase_requisition_id.id,
                'order_line': [(0, 0, {
                    'product_id': order.customer_product_id.sudo().id,
                    'product_qty': order.product_uom_qty,
                    'price_unit': order.price_unit,
                    'location_id': order.location_id.id if order.location_id else None,
                    'name': order.customer_name or '',
                    'date_planned': fields.Date.today(),
                    'taxes_id': [(6, 0, [order.tax_id.sudo().id])] if order.tax_id else [(5,)],
                    'is_seen': order.is_seen,
                }) for order in self.order_line.sudo()],
            })

            # Check if a related purchase requisition exists
            if purchase_order_requisition := self.env['custom.purchase.requisition'].sudo().search(
                    [('unique_id', '=', self.unique_id)]):
                # Update suggest_product_ids
                purchase_order_requisition.sudo().write({
                    'suggest_product_ids': [
                        (0, 0, {
                            'product_id': sale.product_id.sudo().id,
                            'price_unit': sale.price_unit,
                            'vendor_id': self.company_id.id
                        })
                        for sale in self.suggestion_product_ids.sudo()
                    ]
                })
                # Update requisition_order_ids based on existing lines
                for sale in self.order_line:
                    if sale.product_id:
                        existing_line = purchase_order_requisition.requisition_order_ids.filtered(
                            lambda line: line.product_id == sale.product_id
                        )
                        if existing_line:
                            # Update the existing line
                            existing_line.sudo().write({
                                'is_seen': sale.is_seen
                            })
        else:
            # For cases where is_service is True
            for rec in self:
                purchase_order = self.env['custom.purchase.requisition'].sudo().search(
                    [('unique_id', '=', rec.unique_id)], limit=1
                )
                if purchase_order:
                    for line_sale in rec.order_line.sudo():
                        # Create a new line for each sale line in the purchase requisition order
                        self.env['custom.purchase.requisition.order'].sudo().create({
                            'vendor_product_id': line_sale.vendor_product_id.sudo().id,
                            'uom_id': line_sale.uom_id.sudo().id,
                            'description': line_sale.description,
                            'quantity': line_sale.quantity,
                            'unit_price': line_sale.unit_price,
                            'location_id': line_sale.location_id.id if line_sale.location_id else None,
                            'total': line_sale.total,
                            'tax_id': line_sale.tax_id.sudo().id,
                            'vendor_id': rec.company_id.id,
                            'requisition_id': purchase_order.id  # Link to the current purchase order
                        })

        # Update stage to 'requisition_sent'
        self.state = 'requisition_sent'


class CustomSalesRequisitionOrder(models.Model):
    _name = 'custom.sales.requisition.order'
    _description = 'Custom Sales Requisition Order'

    requisition_id = fields.Many2one('custom.sales.requisition', string='Requisition Reference', ondelete='cascade')
    product_category_id = fields.Many2one('product.category', string='Product Category')
    product_id = fields.Many2one('product.product', string='Customer Product',
                                 domain="[('categ_id', '=', product_category_id)]")
    suggestion_product_id = fields.Many2one('product.product', string='Suggestion Product')
    vendor_product_id = fields.Many2one('product.product', string=' Vendor Product')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)



    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', required=True)
    location_id = fields.Many2one('stock.location', string='Vendor Location')
    customer_location_id = fields.Many2one('stock.location', string='Customer Location', readonly=True)

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
    is_seen = fields.Boolean(string="Not Available")

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
            'company_id': self.requisition_id.company_id.id, 'name': self.product_id.name
        })
        return copied_product


class ReceivingDate(models.Model):
    _name = 'sales.receiving.date'
    _description = 'Receiving Date'

    unique_id = fields.Char(string='Unique Identifier')
    receiving_date = fields.Date(string='Receiving Date', required=True)
    requisition_id = fields.Many2one('custom.sales.requisition', string='Requisition Reference', required=True,
                                     ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity = fields.Float(string='Quantity')
    location_id = fields.Many2one('stock.location', string='Location')
    vendor_id = fields.Many2one('res.company', string='Vendors')


class SuggestionProduct(models.Model):
    _name = 'product.suggest'

    product_id = fields.Many2one('product.product')
    price_unit = fields.Float()
    suggest_id = fields.Many2one('custom.sales.requisition', ondelete='cascade')
