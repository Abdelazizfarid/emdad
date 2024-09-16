from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    assigned_location = fields.Many2one(
        'stock.location',
        string='Assigned Location',
        domain=[('usage', '=', 'internal')]
    )

