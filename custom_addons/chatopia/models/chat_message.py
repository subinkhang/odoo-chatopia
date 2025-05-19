from odoo import models, fields

class ChatMessage(models.Model):
    _name = 'chatopia.message'
    _description = 'Chat Message'

    chatwoot_message_id = fields.Integer(string="Chatwoot Message ID")
    inbox_id = fields.Integer(string="Inbox ID")
    chatwoot_conversation_id = fields.Integer(string="Chatwoot Conversation ID")
    sender = fields.Char(string="Sender")
    content = fields.Text(string="Content")
    conversation_id = fields.Many2one('chatopia.conversation', string="Conversation")
    
    message_type = fields.Selection([('user', 'User'), ('admin', 'Admin')], string="Message Type")
    created_at = fields.Datetime(string="Created At")
    is_read = fields.Boolean(string="Is Read", default=False)
