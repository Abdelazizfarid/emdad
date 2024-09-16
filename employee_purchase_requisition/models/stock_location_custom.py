from odoo import models, fields

class StockLocation(models.Model):
    _inherit = 'stock.location'

    address = fields.Char(string='Address')
