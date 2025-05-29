from odoo import models, fields, api, _

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
    inbox_name = fields.Char(related='conversation_id.inbox_name', string="Inbox Name", store=True, readonly=True)
    inbox_names = fields.Json(related='conversation_id.inbox_names', string="Inbox Name", store=True, readonly=True)
    
    message_inbox_names_display = fields.Char(string="Inbox Names (Display)", compute="_compute_message_inbox_names_display")
    
    @api.depends('inbox_names')
    def _compute_message_inbox_names_display(self):
        for rec in self:
            if isinstance(rec.inbox_names, list):
                rec.message_inbox_names_display = ', '.join(rec.inbox_names)
            elif isinstance(rec.inbox_names, str):
                rec.message_inbox_names_display = rec.inbox_names
            else:
                rec.message_inbox_names_display = ''
