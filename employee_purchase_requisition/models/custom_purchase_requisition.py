import uuid

from odoo import models, fields, api,_
from odoo.exceptions import ValidationError

class ResCompany(models.Model):
    _inherit = 'res.company'

    unique_id = fields.Char()
class CustomPurchaseRequisition(models.Model):
    _name = 'custom.purchase.requisition'
    _inherit = ['mail.thread','mail.activity.mixin']
    _description = 'Custom Purchase Requisition'

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'Purchase Requisition {rec.id}'

    active = fields.Boolean(default=True)
    responsible_id = fields.Many2one('res.users', string='Responsible',default=lambda self: self.env.user.id)
    requisition_date = fields.Date(string='Requisition Date', required=True,default=fields.Date.today)
    prepaid_ids = fields.One2many('prepaid','requisition_id')
    received_date = fields.Date(string='Receiving Date')
    requisition_deadline = fields.Date(string='Requisition Deadline', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,default=lambda self: self.env.company.id)
    order_type = fields.Selection([
        ('one_time', 'One-time Supply'),
        ('scheduled', 'Scheduled Supply')
    ], string='Type of Order', required=True)
    suggest_product_ids = fields.One2many('purchase.product.suggest', 'suggest_id')
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
    prepaid_date = fields.Date(string='Prepaid')

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
    single_category_id = fields.Many2one(
        'product.category',
        string='Product Category',
        domain=lambda self: self._compute_category_domain()
    )

    @api.model
    def _compute_category_domain(self):
        # Get category IDs from product templates with products attached
        categories_with_products = self.env['product.template'].search([]).mapped('categ_id').ids
        # Return the domain
        return [('id', 'in', categories_with_products)]



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
    service_vendor_ids = fields.Many2many('res.company','service_rel', string='Service Vendors')
    chosen_vendor_id = fields.Many2one('res.company', string='Chosen Vendor', domain="[('id', 'in', vendor_ids)]")
    chosen_service_vendor_id = fields.Many2one('res.company',relation='other_rel', string='Chosen Service Vendor', domain="[('id', 'in', service_vendor_ids)]")
    total_before_tax = fields.Float(string="Total Before Tax", compute="_compute_totals", store=True)
    tax = fields.Float(string="Tax", compute="_compute_totals", store=True)
    total = fields.Float(string="Total", compute="_compute_totals", store=True)
    notes = fields.Html(string="Notes")
    unique_id = fields.Char()
    approve_sum_products = fields.Boolean(string="Some Products")
    is_service = fields.Boolean("Is Service")
    requisition_order_tab = fields.Boolean()
    receiving_order_order_tab = fields.Boolean()
    prepaid_tab = fields.Boolean()
    tree_readonly = fields.Boolean()

    @api.onchange('order_type')
    def _onchange_order_type(self):
        for line in self.receiving_order_ids:
            line.unlink()

    @api.onchange('supplier_type','single_vendor_id')
    def _compute_chosen_vendor(self):
        for rec in self:
            if rec.supplier_type == 'single' and rec.single_vendor_id:
                rec.chosen_vendor_id = rec.single_vendor_id.id


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

    @api.depends('requisition_order_ids', 'supplier_type', 'single_vendor_id')
    def _compute_vendor_ids(self):
        for record in self:
            if record.supplier_type == 'single':
                record.vendor_ids = [record.single_vendor_id.id] if record.single_vendor_id else []
            else:
                record.vendor_ids = record.requisition_order_ids.mapped('vendor_ids').ids

    @api.depends('requisition_order_ids')
    def _compute_vendors_offers(self):
        for record in self:
            offers = []
            vendor_totals = {}

            # Loop through requisition_order_ids and sum totals per vendor
            for line in record.requisition_order_ids:
                if line.vendor_ids:
                    for vendor in line.vendor_ids:
                        if vendor not in vendor_totals:
                            vendor_totals[vendor] = 0
                        vendor_totals[vendor] += line.total  # Assuming `total` is the price of the line

            # Format the offers string
            for vendor, total in vendor_totals.items():
                offers.append(f"{vendor.name}: {total} EGP")

            # Join offers for display
            record.vendors_offers = "\n".join(offers)

    @api.model
    def create(self, vals):
        # sourcery skip: merge-duplicate-blocks, reintroduce-else, remove-redundant-if, split-or-ifs, swap-if-else-branches
        # Call super to create the record first
        requisition = super(CustomPurchaseRequisition, self).create(vals)

        vals['name'] = f"P.Req {self.env['ir.sequence'].next_by_code('custom.purchase.requisition')}"

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
        if requisition.supplier_type == 'single' and not requisition.is_service:
            if not requisition.single_vendor_id:
                raise ValidationError("Vendor must be specified for single supply type.")
            requisition.chosen_vendor_id = requisition.single_vendor_id.id
        else:
            for line in requisition.requisition_order_ids:
                if not line.vendor_ids:
                    raise ValidationError("Each requisition line must have a vendor specified for this supply type.")

        if requisition.is_service and not requisition.service_vendor_ids:
            raise ValidationError("You Must Choose Vendors You Want Their Offers")

        ordered_product_list = [line.product_id for line in requisition.requisition_order_ids]
        for line_add in requisition.receiving_order_ids:
            if line_add.product_id not in ordered_product_list:
                raise ValidationError(_(f"You Dont Order {line_add.product_id.name}"))

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
            if requisition.supplier_type == 'single' and not requisition.is_service:
                if not requisition.single_vendor_id:
                    raise ValidationError("Vendor must be specified for single supply type.")
            else:
                for line in requisition.requisition_order_ids:
                    if not line.vendor_ids:
                        raise ValidationError(
                            "Each requisition line must have a vendor specified for this supply type.")

            ordered_product_list = [line.product_id for line in self.requisition_order_ids]
            for line_add in self.receiving_order_ids:
                if line_add.product_id not in ordered_product_list:
                    raise ValidationError(_(f"You Dont Order {line_add.product_id.name}"))
            # If you want to compare quantities per product
        return result

    def action_submit_requisition(self):
        self.tree_readonly = True
        # Generate a unique ID for the requisition
        self.unique_id = str(uuid.uuid4())
        if self.order_type == 'scheduled':

            # If you want to compare quantities per product
            for line_ordered in self.requisition_order_ids:
                # Find the matching receiving order line for the same product
                matching_receiving_lines = self.receiving_order_ids.filtered(
                    lambda l: l.product_id == line_ordered.product_id)

                # Sum the quantities for the matching product
                received_quantity_per_product = sum(matching_receiving_lines.mapped('quantity'))

                if received_quantity_per_product != line_ordered.quantity:
                    raise ValidationError(_(
                        "The received quantity for product %s does not match the ordered quantity."
                    ) % line_ordered.product_id.display_name)
        for line in self.requisition_order_ids:
            if not line.quantity:
                raise ValidationError(_("Quantity Is Required"))
        if self.supplier_type == 'single' and not self.is_service:
            # Use the single vendor
            vendors = [self.single_vendor_id] if self.single_vendor_id else []
        elif self.supplier_type == 'multiple' and not self.is_service:
            # Gather unique vendors from the requisition orders
            vendors = list(set(self.requisition_order_ids.mapped('vendor_ids')))
        else:
            vendors = self.service_vendor_ids  # Service vendors

        # Loop through each vendor
        for vendor in vendors:
            sales_requisition = self.env['custom.sales.requisition'].sudo().create({
                'requisition_date': self.requisition_date,
                'total_before_tax': self.total_before_tax,
                'tax': self.tax,
                'total': self.total,
                'single_vendor_id': self.single_vendor_id.id if self.single_vendor_id else False,
                'single_category_id': self.single_category_id.id if self.single_category_id else False,
                'products_category_type': self.products_category_type,
                'single_location_id': self.single_location_id.id if self.single_location_id else False,
                'supplier_type': self.supplier_type,
                'payment_term': self.payment_term,
                'prepaid_date': self.prepaid_date,
                'notes': self.notes,
                'unique_id': self.unique_id,
                'related_purchase_requisition_id':self.id,
                'requisition_deadline': self.requisition_deadline,
                'customer_id': self.company_id.id,
                'company_id': vendor.id,
                'order_type': self.order_type,
                'payment_method': self.payment_method,
                'supply_type': self.supply_type,
                'source_location_id': self.source_location_id.id if self.source_location_id else False,
                'destination_location_id': self.destination_location_id.id if self.destination_location_id else False,
                'delivery_to_id': self.delivery_to_id.id if self.delivery_to_id else False,
                'internal_picking_id': self.internal_picking_id.id if self.internal_picking_id else False,
            })

            if self.supplier_type == 'single':
                # No filtering for a single vendor
                filtered_orders = self.requisition_order_ids
            else:
                # Filter purchase orders based on the vendor
                filtered_orders = self.requisition_order_ids.filtered(lambda o: vendor in o.vendor_ids)
                print(filtered_orders)
            # Create lines for the sales requisition
            for order in filtered_orders:
                self.env['custom.sales.requisition.order'].sudo().create({
                    'requisition_id': sales_requisition.id,
                    'product_category_id': order.product_category_id.id,
                    'product_id': order.product_id.id,
                    'uom_id': order.uom_id.id,
                    'description': order.description,
                    'quantity': order.quantity,
                    'tax_id': order.tax_id.id,
                    'customer_location_id': order.location_id.id
                })

            if self.order_type == 'scheduled':
                # Filter and create receiving orders
                filtered_products = self.receiving_order_ids.filtered(lambda o: o.vendor_id.id == vendor.id)
                for product in filtered_products:
                    unique_id = str(uuid.uuid4())  # Generate a unique ID
                    product.write({'unique_id': unique_id})  # Set the unique ID

                    self.env['sales.receiving.date'].sudo().create({
                        'requisition_id': sales_requisition.id,
                        'receiving_date': product.receiving_date,
                        'product_id': product.product_id.id,
                        'uom_id': product.uom_id.id,
                        'quantity': product.quantity,
                        'unique_id': unique_id,
                        'location_id': product.location_id.id
                    })
        # print(x)
        # Check for excess received quantities
        for order in self.requisition_order_ids:
            total_ordered = sum(
                line.quantity for line in self.requisition_order_ids if line.product_id == order.product_id)
            total_received = sum(
                received.quantity for received in self.receiving_order_ids if received.product_id == order.product_id)

            if total_received > total_ordered:
                raise ValidationError(
                    _("Received quantity for {} exceeds ordered quantity.").format(order.product_id.name))

        # Update stage after submission
        self.stage = 'requisition_sent'

    def action_approve_offer(self):
        if self.is_service and not self.chosen_service_vendor_id:
            raise ValidationError("Please select a vendor to approve the offer.")
        if not self.is_service and not self.chosen_vendor_id:
            raise ValidationError("Please select a vendor to approve the offer.")
        # Create a purchase order for the chosen vendor
        if not self.is_service:
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
                }) for line in self.requisition_order_ids if self.chosen_vendor_id in line.vendor_ids or self.chosen_vendor_id==self.single_vendor_id],
            })
            self.env['sale.order'].sudo().create({
                'partner_id': self.company_id.partner_id.id,  # The current company will be the customer
                'company_id': self.chosen_vendor_id.id,  # The chosen vendor will be the selling company
                'date_order': fields.Datetime.now(),
                'order_line': [(0, 0, {
                    'product_id': line.vendor_product_id.id,
                    'product_uom_qty': line.quantity,
                    'price_unit': line.unit_price,
                    'name': line.description or '',
                    'product_uom': line.uom_id.id,
                }) for line in self.requisition_order_ids if self.chosen_vendor_id in line.vendor_ids ],
            })
            self.stage = 'purchase_order_created'
            return {
                'name': 'Purchase Order',
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_mode': 'form',
                'res_id': purchase_order.id,
            }
        else:
            sale_order = self.env['sale.order'].sudo().create({
                'partner_id': self.company_id.partner_id.id,  # The current company will be the customer
                'company_id': self.chosen_service_vendor_id.id,  # The chosen vendor will be the selling company
                'date_order': fields.Datetime.now(),
                'order_line': [(0, 0, {
                    'product_id': line.vendor_product_id.id,
                    'product_uom_qty': line.quantity,
                    'price_unit': line.unit_price,
                    'name': line.description or '',
                    'product_uom': line.uom_id.id,
                }) for line in self.requisition_order_ids if self.chosen_service_vendor_id in line.vendor_ids],
            })

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
            'requisition_order_ids': self.requisition_order_ids.ids,
            'receiving_order_ids': self.receiving_order_ids.ids,
            'source_location_id': self.source_location_id.id,
            'destination_location_id': self.destination_location_id.id,
            'delivery_to_id': self.delivery_to_id.id,
            'internal_picking_id': self.internal_picking_id.id,
            'address': self.address,
            'vendors_offers': self.vendors_offers,
            'vendor_ids': self.vendor_ids.ids,
            'service_vendor_ids': self.service_vendor_ids.ids,
            'chosen_vendor_id': self.chosen_vendor_id.name,
            'chosen_service_vendor_id': self.chosen_service_vendor_id.id,
            'total_before_tax': self.total_before_tax,
            'tax': self.tax,
            'total': self.total,
            'notes': self.notes,
            'approve_sum_products': self.approve_sum_products,
            'is_service': self.is_service,
            'requisition_order_tab': self.requisition_order_tab,
            'receiving_order_order_tab': self.receiving_order_order_tab,
            'prepaid_tab': self.prepaid_tab,
        }
        print(self.requisition_order_ids.ids)
        return self.env.ref('employee_purchase_requisition.action_report_print_purchase_requisition').report_action(self,data=data)


class CustomPurchaseRequisitionOrder(models.Model):
    _name = 'custom.purchase.requisition.order'
    _description = 'Custom Purchase Requisition Order'

    requisition_id = fields.Many2one('custom.purchase.requisition', string='Requisition Reference')
    order_type = fields.Selection([
        ('one_time', 'One-time Supply'),
        ('scheduled', 'Scheduled Supply')
    ], string='Type of Order', related='requisition_id.order_type')
    product_category_id = fields.Many2one('product.category', string='Product Category')
    image_1920 = fields.Image("Image", max_width=1920, max_height=1920, related='product_id.image_1920')
    product_id = fields.Many2one('product.product', string='Product')
    vendor_product_id = fields.Many2one('product.product', string='Vendor Product')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity')
    # sum_quantities = fields.Float(string='Some Quantities')
    vendor_ids = fields.Many2many('res.company', string='Vendors',)
    location_id = fields.Many2one('stock.location', string='Customer Location',domain=[('usage', '=', 'internal')])
    vendor_location_id = fields.Many2one('stock.location', string='Vendor Location',readonly=True)
    # Add a related field to get the address from the destination_location_id
    address = fields.Char(related='location_id.address', string='Destination Address', readonly=True)
    is_seen = fields.Boolean()
    # Add a related field to get the value of supply_type from the parent requisition
    supply_type = fields.Selection(related='requisition_id.supply_type', string="Supply Type", store=True)

    # Unit price comes from sales requisition, and is readonly in purchase requisition
    unit_price = fields.Float(string='Unit Price')
    tax_id = fields.Many2one('account.tax', string='Tax')


    # Computed field for total (unit_price * quantity)
    total = fields.Float(string='Total', compute='_compute_total', store=True)

    # Add unique identifier field to link with Sales Requisition
    unique_id = fields.Char(string='Unique Identifier')
    deadline = fields.Date(string='Deadline Date')

    def copy_line(self):
        return self.copy()

    def address_icon(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info' if self.location_id.address else 'danger',
                'title': _("Destination Address") if self.location_id.address else _(""),
                'message': f"{self.location_id.address}" if self.location_id.address else "No Address In This Location",
                'next': {
                    'type': 'ir.actions.act_window_close'
                },
            }
        }


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

    unique_id = fields.Char(string='Unique Identifier')
    requisition_order_id = fields.Many2one('custom.purchase.requisition.order', string='Requisition Order')
    receiving_date = fields.Date(string='Receiving Date', required=True)
    requisition_id = fields.Many2one('custom.purchase.requisition', string='Requisition Reference', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity = fields.Float(string='Quantity', required=True)
    location_id = fields.Many2one('stock.location', string='Location')
    vendor_id = fields.Many2one('res.company', string='Vendors')

    # receiving_ids = fields.One2many('rec.date', 'rec_date_id')
# class ProductCategory(models.Model):
#     _inherit = 'product.category'
#
#     product_count = fields.Integer(
#         '# Products', compute='_compute_product_count',store=True,
#         help="The number of products under this category (Does not consider the children categories)")
#
#
#     def _compute_product_count(self):
#         read_group_res = self.env['product.template']._read_group([('categ_id', 'child_of', self.ids)], ['categ_id'], ['__count'])
#         group_data = {categ.id: count for categ, count in read_group_res}
#         for categ in self:
#             product_count = 0
#             for sub_categ_id in categ.search([('id', 'child_of', categ.ids)]).ids:
#                 product_count += group_data.get(sub_categ_id, 0)
#             categ.product_count = product_count

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    related_purchase_requisition_id = fields.Many2one('custom.purchase.requisition',"Related Requisition")

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    is_seen = fields.Boolean(string="Not Available?")

class PurchaseSuggestionProduct(models.Model):
    _name = 'purchase.product.suggest'

    product_id = fields.Many2one('product.product')
    price_unit = fields.Float()
    suggest_id = fields.Many2one('custom.purchase.requisition')
    vendor_id = fields.Many2one('res.company')

    def create_product(self):
        self.env['product.product'].sudo().create({
            'name':self.product_id.name,
            'detailed_type':self.product_id.detailed_type,
            'company_id':self.env.user.company_id.id
        })

class Prepaid(models.Model):
    _name = 'prepaid'

    deadline = fields.Date(string='Deadline Date')
    requisition_id = fields.Many2one('custom.purchase.requisition')


class PrepareReceivingDate(models.Model):
    _name = 'prepare.receiving.date'

    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity = fields.Float(string='Quantity')
    requisition_id = fields.Many2one('custom.purchase.requisition')
    receiving_date_lines_ids = fields.One2many('prepare.receiving.date.lines', 'prepare_id', string='Receiving Dates Ids')
    requisition_order_id = fields.Many2one('custom.purchase.requisition.order', string='Requisition Order')
    location_id = fields.Many2one('stock.location', string='Location', domain=[('usage', '=', 'internal')])

    def add_receiving_dates(self):
        # Calculate the total quantity already created in the target model for the related requisition_id
        total_existing_quantity = sum(self.env['receiving.date'].search([
            ('requisition_id', '=', self.requisition_id.id),
            ('requisition_order_id', '=', self.requisition_order_id.id),
            ('product_id', '=', self.product_id.id),
        ]).mapped('quantity'))

        # Check if the total existing quantity is already equal to or exceeds the parent model's quantity
        if total_existing_quantity >= self.quantity:
            raise ValidationError('Cannot create more records: total created quantity already equals or exceeds the required quantity.')

        # Validate that the total line quantity matches the wizard's total quantity
        total_line_quantity = sum(self.receiving_date_lines_ids.mapped('quantity'))
        if total_line_quantity != self.quantity:
            raise ValidationError('Quantity of Lines Must Be Equal to Total Quantity')

        for line in self.receiving_date_lines_ids:
            # Check if adding this line would exceed the required quantity
            if total_existing_quantity + line.quantity > self.quantity:
                raise ValidationError(
                    f"Adding this line exceeds the required quantity ({self.quantity}). Current total: {total_existing_quantity}."
                )

            # Create the new record
            self.env['receiving.date'].create({
                'receiving_date': line.receiving_date,
                'product_id': self.product_id.id,
                'uom_id': line.uom_id.id,
                'quantity': line.quantity,
                'location_id': line.location_id.id,
                'vendor_id': line.vendor_id.id,
                'requisition_id': self.requisition_id.id,
                'requisition_order_id': self.requisition_order_id.id,
            })

            # Update the total existing quantity after each creation
            total_existing_quantity += line.quantity


class PrepareReceivingDateLines(models.Model):
    _name = 'prepare.receiving.date.lines'

    prepare_id = fields.Many2one('prepare.receiving.date', string='Prepare Id')
    requisition_order_id = fields.Many2one('custom.purchase.requisition.order', string='Requisition Order')

    unique_id = fields.Char(string='Unique Identifier')
    receiving_date = fields.Date(string='Receiving Date', required=True)
    requisition_id = fields.Many2one('custom.purchase.requisition', string='Requisition Reference', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)
    quantity = fields.Float(string='Quantity', required=True)
    location_id = fields.Many2one('stock.location', string='Location')
    vendor_id = fields.Many2one('res.company', string='Vendors')

