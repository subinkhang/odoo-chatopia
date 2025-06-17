# models/chat_message.py
from odoo import models, fields, api, _, tools


class ChatMessage(models.Model):
    _name = 'chatopia.message'
    _description = 'Chat Message (Raw from Integration)' # Cập nhật description
    _order = 'created_at desc, id desc' # Thêm order

    chatwoot_message_id = fields.Integer(string="Chatwoot Message ID")
    inbox_id = fields.Integer(string="Inbox ID") # Chatwoot Inbox ID
    chatwoot_conversation_id = fields.Integer(string="Chatwoot Conversation ID") # ID của conversation gốc bên Chatwoot
    sender = fields.Char(string="Sender Name") # Tên người gửi gốc
    content = fields.Text(string="Content")
    conversation_id = fields.Many2one('chatopia.conversation', string="Chatopia Conversation", ondelete='cascade')
    message_type = fields.Selection([
        ('user', 'From User/Contact'), # Tin nhắn từ khách hàng
        ('admin', 'From Agent/Odoo'),  # Tin nhắn từ agent (qua Odoo hoặc Chatwoot)
        ('outgoing', 'Outgoing (Chatwoot perspective)'), # Nếu phân biệt rõ hơn
        ('incoming', 'Incoming (Chatwoot perspective)')
        ], string="Message Type")
    created_at = fields.Datetime(string="Created At", default=fields.Datetime.now)
    is_read = fields.Boolean(string="Is Read", default=False) # Trạng thái đọc từ Chatwoot
    # Trường này để link tới mail.message tương ứng nếu có
    mail_message_id_link = fields.Many2one('mail.message', string="Linked Odoo Message", readonly=True)
    # Các trường related này có thể vẫn hữu ích
    inbox_name = fields.Char(related='conversation_id.inbox_name', string="Conv. Inbox Name", store=True, readonly=True)
    inbox_names = fields.Json(related='conversation_id.inbox_names', string="Conv. Inbox Names", store=True, readonly=True) # Sửa string
    message_inbox_names_display = fields.Char(string="Inbox Names (Display)", compute="_compute_message_inbox_names_display")
    message_from = fields.Selection([
        ('1', 'Facebook - Fruity'),
        ('2', 'Facebook - Khám Phá Di Tích cùng GenZ'),
        ('3', 'Zalo - TopNet'),
        ('', 'Other'),
    ], string="Message From", help="Message from", default='')
    
    @api.depends('inbox_names')
    def _compute_message_inbox_names_display(self):
        for rec in self:
            if isinstance(rec.inbox_names, list):
                rec.message_inbox_names_display = ', '.join(rec.inbox_names)
            elif isinstance(rec.inbox_names, str):
                rec.message_inbox_names_display = rec.inbox_names
            else:
                rec.message_inbox_names_display = ''
                
                
    @api.model_create_multi
    def create(self, vals_list):
        # Gọi create gốc để tạo các bản ghi chatopia.message trước
        messages = super().create(vals_list)
        
        # Sau khi tạo, duyệt qua các message mới và post chúng vào chatter
        for msg_raw in messages:
            if msg_raw.conversation_id and msg_raw.content: # Đảm bảo có conversation và nội dung
                # _logger.info(f"ChatMessage create: Auto-posting chatopia.message ID {msg_raw.id} to chatter of conv {msg_raw.conversation_id.id}")
                
                conv = msg_raw.conversation_id
                author_partner_id = False
                email_from_formatted = self.env.user.company_id.email_formatted or "chatopia.import@example.com"
                
                if msg_raw.sender:
                    partner = self.env['res.partner'].search([('name', '=ilike', msg_raw.sender)], limit=1)
                    if partner:
                        author_partner_id = partner.id
                        email_from_formatted = tools.formataddr((partner.name, partner.email or email_from_formatted.split('@')[-1]))
                    else:
                        email_from_formatted = tools.formataddr((msg_raw.sender, email_from_formatted.split('@')[-1]))
                
                message_type_for_chatter = 'comment'
                subtype_xmlid = 'mail.mt_comment'

                # Quan trọng: Chuẩn bị context để tránh gửi ngược lại Chatwoot
                # nếu message_post của conversation có logic đó
                post_context = {
                    'from_chatwoot_sync': True, # Đánh dấu là từ hệ thống, không phải user Odoo gửi mới
                    'mail_create_nosubscribe': True,
                    'mail_post_autofollow': False,
                    # 'force_ compañía': self.env.company.id, # Nếu cần cho multi-company
                }
                
                post_kwargs = {
                    'body': msg_raw.content,
                    'author_id': author_partner_id,
                    'email_from': email_from_formatted,
                    'message_type': message_type_for_chatter,
                    'subtype_xmlid': subtype_xmlid,
                    'date': msg_raw.created_at, # Đặt ngày tạo cho mail.message
                    # 'attachment_ids': [], # Nếu có attachments
                }
                
                try:
                    posted_mail_message = conv.with_context(**post_context).message_post(**post_kwargs)
                    if posted_mail_message:
                        msg_raw.sudo().write({'mail_message_id_link': posted_mail_message.id}) # Dùng sudo nếu cần
                        # _logger.info(f"ChatMessage create: Auto-posted to mail.message ID {posted_mail_message.id}")
                except Exception as e:
                    pass
                    # _logger.error(f"ChatMessage create: Error auto-posting chatopia.message ID {msg_raw.id} to chatter: {e}", exc_info=True)
        return messages