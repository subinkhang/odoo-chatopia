from odoo import models, fields

class ChatopiaMessage(models.Model):
    _name = 'chatopia.message'
    _description = 'Chatopia Message'

    content = fields.Text(string='Message Content')
    channel = fields.Char(string='Channel')
    sender = fields.Char(string='Sender')
    created_at = fields.Datetime(string='Created At', default=fields.Datetime.now)