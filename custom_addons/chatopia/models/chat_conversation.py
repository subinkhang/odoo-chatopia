# models/chat_conversation.py
from odoo import models, fields, api, _, tools # Thêm tools
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
import re

_logger = logging.getLogger(__name__)

class ChatConversation(models.Model):
    _name = 'chatopia.conversation'
    _description = 'Chat Conversation'
    _order = 'last_message_display_time desc, id desc' # Đổi tên last_message_time để tránh xung đột tiềm ẩn
    _inherit = ['mail.thread', 'mail.activity.mixin'] # KẾ THỪA TỪ MAIL.THREAD
    is_starred = fields.Boolean(string="Starred", tracking=True, copy=False,
                                help="Mark this conversation as important (starred).")

    name = fields.Char(string="Conversation Name", tracking=True) # Thêm tracking
    chatwoot_conversation_id = fields.Integer(string="Chatwoot Conversation ID", readonly=True, tracking=True)
    chatwoot_conversation_ids = fields.Json(string="Chatwoot Conversation IDs", readonly=True, help="Danh sách các Chatwoot Conversation ID liên quan (dạng mảng số nguyên).")
    inbox_name = fields.Char(string="Inbox Name", readonly=True)
    sender_name = fields.Char(string="Sender Name", readonly=True)
    inbox_names = fields.Json(string="Inbox Names", readonly=True)
    sender_names = fields.Json(string="Sender Names", readonly=True)
    contact_id = fields.Many2one('res.partner', string="Contact", tracking=True) # Bỏ required=True nếu không phải lúc nào cũng có
    contact_ids = fields.Many2many(
        'res.partner',
        'chatopia_conversation_res_partner_rel',
        'conversation_id',
        'partner_id',
        string="Contacts",
        tracking=True
    )
    # Đổi tên message_ids của bạn để tránh xung đột với message_ids từ mail.thread
    chatopia_message_ids = fields.One2many('chatopia.message', 'conversation_id', string="Chatopia Raw Messages")
    
    # message_content này sẽ được dùng bởi nút "Send" tùy chỉnh của bạn
    # Nếu bạn muốn dùng hoàn toàn composer của Odoo, bạn có thể bỏ trường này và nút "Send" tùy chỉnh
    # và điều chỉnh logic send_message_to_chatwoot để được gọi từ message_post.
    # Hiện tại, chúng ta giữ nó để logic send_message gốc vẫn hoạt động qua nút bấm.
    message_content_to_send = fields.Text(string="Message to Send")

    x_chatwoot_contact_id = fields.Char(string="Chatwoot Contact ID", readonly=True)
    x_chatwoot_inbox_id = fields.Integer(string="Chatwoot Inbox ID", readonly=True)
    
    # Các trường này sẽ được tính toán lại dựa trên mail.message
    last_message_display_content = fields.Text(string="Last Message Content", compute="_compute_last_message_display_fields", store=False)
    last_message_display_time = fields.Datetime(string="Last Message Time", compute="_compute_last_message_display_fields", store=False) # Sẽ sort theo trường này

    avatar = fields.Binary(string="Avatar") # Giữ lại nếu bạn muốn hiển thị avatar tùy chỉnh trên form view
    
    inbox_names_display = fields.Char(string="Inbox Names (Display)", compute="_compute_inbox_names_display")
    sender_names_display = fields.Char(string="Sender Names (Display)", compute="_compute_sender_names_display")
    active = fields.Boolean(default=True) # Thêm trường active nếu chưa có

    # THÊM TRƯỜNG user_id VÀO ĐÂY
    user_id = fields.Many2one(
        'res.users', string='Responsible User',
        default=lambda self: self.env.user, # Tùy chọn: đặt người dùng hiện tại làm mặc định
        tracking=True
    )
    
    related_chatwoot_conversations = fields.Json(
        string="Related Chatwoot Conversations Details",
        default=list, # Mặc định là một danh sách rỗng
        help="List of related Chatwoot conversation details, including their original inbox ID and name. "
             "Example: [{'id': 11, 'inbox_id': 1, 'inbox_name': 'Facebook - Fruity'}]"
    )

    @api.depends('related_chatwoot_conversations')
    def _compute_legacy_chatwoot_ids(self):
        for record in self:
            if isinstance(record.related_chatwoot_conversations, list):
                record.chatwoot_conversation_ids = [item.get('id') for item in record.related_chatwoot_conversations if isinstance(item, dict) and item.get('id')]
            else:
                record.chatwoot_conversation_ids = []

    @api.depends('message_ids.date', 'message_ids.body') # message_ids này là từ mail.thread
    def _compute_last_message_display_fields(self):
        for conv in self:
            last_msg = self.env['mail.message'].search([
                ('model', '=', self._name),
                ('res_id', '=', conv.id),
                ('message_type', 'in', ['comment', 'email']), # Chỉ tin nhắn thực tế, không phải notification
                ('body', '!=', False),
                ('body', '!=', '<p><br></p>') # Bỏ qua tin nhắn trống
            ], order='date desc', limit=1)
            if last_msg:
                conv.last_message_display_content = tools.html2plaintext(last_msg.body).strip() if last_msg.body else ''
                conv.last_message_display_time = last_msg.date
            else:
                # Nếu không có mail.message, thử fallback về chatopia_message_ids nếu có
                last_chatopia_msg = self.env['chatopia.message'].search([
                    ('conversation_id', '=', conv.id)
                ], order='created_at desc', limit=1)
                if last_chatopia_msg:
                    conv.last_message_display_content = last_chatopia_msg.content
                    conv.last_message_display_time = last_chatopia_msg.created_at
                else:
                    conv.last_message_display_content = ''
                    conv.last_message_display_time = False

    @api.depends('sender_names')
    def _compute_sender_names_display(self):
        for rec in self:
            if rec.sender_names and isinstance(rec.sender_names, list):
                rec.sender_names_display = ', '.join(rec.sender_names)
            elif isinstance(rec.sender_names, str):
                rec.sender_names_display = rec.sender_names
            else:
                rec.sender_names_display = ''

    @api.depends('inbox_names')
    def _compute_inbox_names_display(self):
        for rec in self:
            if rec.inbox_names and isinstance(rec.inbox_names, list):
                rec.inbox_names_display = ', '.join(rec.inbox_names)
            elif isinstance(rec.inbox_names, str):
                rec.inbox_names_display = rec.inbox_names
            else:
                rec.inbox_names_display = ''

    @api.model
    def _get_inbox_name_by_id(self, inbox_id_int):
        if not inbox_id_int:
            return _("Unknown Inbox")
        try:
            message_model = self.env['chatopia.message']
            if 'message_from' in message_model._fields: # Giả sử tên trường selection là message_from
                selection_options = dict(message_model._fields['message_from'].selection)
                return selection_options.get(str(inbox_id_int), _("Other/ID: %s") % inbox_id_int)
            else:
                _logger.warning("Field for inbox selection not found on 'chatopia.message' for inbox name lookup.")
                return _("Inbox ID: %s") % inbox_id_int
        except Exception as e:
            _logger.error("Error getting inbox name for ID %s: %s", inbox_id_int, e)
            return _("Error Inbox ID: %s") % inbox_id_int

    def action_merge_selected(self):
        _logger.info(">>> MERGE: Starting action for %s conversations.", len(self))

        if len(self) < 2:
            _logger.warning(">>> MERGE: Less than 2 conversations selected.")
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Selection Error'),
                'message': _("Please select at least two conversations to merge."),
                'type': 'warning', 'sticky': False,
            }}

        # Xác định master conversation (ví dụ: cái được tạo sớm nhất hoặc cập nhật gần nhất)
        # Hoặc đơn giản là self[0] nếu thứ tự chọn quan trọng.
        # Để ổn định, sắp xếp theo một tiêu chí, ví dụ create_date
        sorted_conversations = self.sorted(key=lambda r: (r.create_date or fields.Datetime.now(), r.id))
        master_conversation = sorted_conversations[0]
        conversations_to_merge_records = sorted_conversations[1:]

        _logger.info(">>> MERGE: Master Odoo ID: %s (Primary CW ID: %s)", 
                     master_conversation.id, master_conversation.chatwoot_conversation_id)
        _logger.info(">>> MERGE: Conversations to merge Odoo IDs: %s", conversations_to_merge_records.ids)

        with self.env.cr.savepoint():
            try:
                # --- 0. Chuẩn bị dữ liệu để gộp vào master ---
                all_contacts_to_link_ids = set(master_conversation.contact_ids.ids)
                all_inbox_names_set = set(master_conversation.inbox_names or [])
                all_sender_names_set = set(master_conversation.sender_names or [])
                
                # Chuẩn bị dồn related_chatwoot_conversations
                # Mỗi item: {'id': <int>, 'inbox_id': <int>, 'inbox_name': <str>}
                merged_related_cw_details = []
                seen_cw_conv_ids_for_details = set()

                # Hàm helper nội bộ để thêm chi tiết một cách nhất quán
                def add_cw_detail(cw_id, inbox_id, inbox_name_str):
                    if cw_id and cw_id not in seen_cw_conv_ids_for_details:
                        # Nếu inbox_name_str chưa có, thử tra cứu từ inbox_id
                        final_inbox_name = inbox_name_str
                        if not final_inbox_name and inbox_id:
                            final_inbox_name = self._get_inbox_name_by_id(inbox_id)
                        elif not final_inbox_name:
                            final_inbox_name = _("Unknown Inbox")
                            
                        merged_related_cw_details.append({
                            'id': cw_id,
                            'inbox_id': inbox_id,
                            'inbox_name': final_inbox_name
                        })
                        seen_cw_conv_ids_for_details.add(cw_id)

                # Xử lý master conversation trước
                add_cw_detail(master_conversation.chatwoot_conversation_id, 
                              master_conversation.x_chatwoot_inbox_id, 
                              master_conversation.inbox_name) # inbox_name của master là một nguồn
                if isinstance(master_conversation.related_chatwoot_conversations, list):
                    for detail in master_conversation.related_chatwoot_conversations:
                        if isinstance(detail, dict) and detail.get('id'):
                            add_cw_detail(detail.get('id'), detail.get('inbox_id'), detail.get('inbox_name'))
                
                # Xử lý các conversations sẽ bị merge
                for conv in conversations_to_merge_records:
                    # Dồn contacts
                    if conv.contact_id:
                        all_contacts_to_link_ids.add(conv.contact_id.id)
                    all_contacts_to_link_ids.update(conv.contact_ids.ids)
                    
                    # Dồn inbox_names (cho trường Json `inbox_names`)
                    if isinstance(conv.inbox_names, list):
                        all_inbox_names_set.update(conv.inbox_names)
                    
                    # Dồn sender_names (cho trường Json `sender_names`)
                    if isinstance(conv.sender_names, list):
                        all_sender_names_set.update(conv.sender_names)

                    # Dồn related_chatwoot_conversations
                    add_cw_detail(conv.chatwoot_conversation_id, 
                                  conv.x_chatwoot_inbox_id, 
                                  conv.inbox_name)
                    if isinstance(conv.related_chatwoot_conversations, list):
                        for detail in conv.related_chatwoot_conversations:
                            if isinstance(detail, dict) and detail.get('id'):
                                add_cw_detail(detail.get('id'), detail.get('inbox_id'), detail.get('inbox_name'))
                
                # Hoàn thiện danh sách
                final_contact_ids_list = list(all_contacts_to_link_ids)
                final_inbox_names_list = sorted(list(all_inbox_names_set))
                final_sender_names_list = sorted(list(all_sender_names_set))
                # Sắp xếp final_related_cw_details theo ID
                merged_related_cw_details.sort(key=lambda x: x['id'])

                # --- 1. Cập nhật các trường trên master_conversation ---
                vals_to_update_master = {}
                
                if final_contact_ids_list:
                    vals_to_update_master['contact_ids'] = [(6, 0, final_contact_ids_list)]
                    if not master_conversation.contact_id and final_contact_ids_list:
                        vals_to_update_master['contact_id'] = final_contact_ids_list[0]
                
                if final_inbox_names_list:
                    vals_to_update_master['inbox_names'] = final_inbox_names_list
                    # Cập nhật inbox_name chính của master (Char)
                    # Ưu tiên inbox_name hiện tại của master nếu nó có trong list đã gộp
                    # Nếu không, lấy cái đầu tiên từ list đã gộp
                    if master_conversation.inbox_name and master_conversation.inbox_name in final_inbox_names_list:
                        pass # Giữ nguyên inbox_name của master
                    elif final_inbox_names_list:
                        vals_to_update_master['inbox_name'] = final_inbox_names_list[0]
                    else:
                        vals_to_update_master['inbox_name'] = False


                if final_sender_names_list:
                    vals_to_update_master['sender_names'] = final_sender_names_list
                    if master_conversation.sender_name and master_conversation.sender_name in final_sender_names_list:
                        pass
                    elif final_sender_names_list:
                        vals_to_update_master['sender_name'] = final_sender_names_list[0]
                    else:
                        vals_to_update_master['sender_name'] = False
                
                # Cập nhật related_chatwoot_conversations (trường JSON mới)
                if merged_related_cw_details:
                    vals_to_update_master['related_chatwoot_conversations'] = merged_related_cw_details
                    _logger.info(">>> MERGE: Master Odoo ID %s will be updated with related_chatwoot_conversations: %s", 
                                 master_conversation.id, merged_related_cw_details)
                
                # chatwoot_conversation_id (Integer) của master giữ nguyên
                # x_chatwoot_inbox_id của master cũng giữ nguyên (là inbox của ID chính đó)

                if vals_to_update_master:
                    master_conversation.write(vals_to_update_master)
                    _logger.info(">>> MERGE: Master Odoo ID %s updated with merged fields.", master_conversation.id)

                # --- 2. Gộp chatopia.message ---
                chatopia_messages_to_relink = self.env['chatopia.message'].search([
                    ('conversation_id', 'in', conversations_to_merge_records.ids)
                ])
                if chatopia_messages_to_relink:
                    _logger.info(">>> MERGE: Relinking %s chatopia.message records to master Odoo ID %s...", len(chatopia_messages_to_relink), master_conversation.id)
                    chatopia_messages_to_relink.write({'conversation_id': master_conversation.id})
                
                # --- 3. Gộp mail.message ---
                mail_messages_to_relink = self.env['mail.message'].search([
                    ('model', '=', self._name),
                    ('res_id', 'in', conversations_to_merge_records.ids)
                ])
                if mail_messages_to_relink:
                    _logger.info(">>> MERGE: Relinking %s mail.message records to master Odoo ID %s...", len(mail_messages_to_relink), master_conversation.id)
                    mail_messages_to_relink.write({'res_id': master_conversation.id})
                
                # --- 4. Gộp followers và activities ---
                for conv_to_merge in conversations_to_merge_records:
                    current_master_follower_partner_ids = master_conversation.message_follower_ids.mapped('partner_id').ids
                    for follower in conv_to_merge.message_follower_ids:
                        if follower.partner_id and follower.partner_id.id not in current_master_follower_partner_ids:
                            try:
                                master_conversation.message_subscribe(partner_ids=[follower.partner_id.id], subtype_ids=follower.subtype_ids.ids)
                            except Exception as e_f:
                                _logger.warning(">>> MERGE: Could not subscribe partner %s to master Odoo ID %s: %s", follower.partner_id.id, master_conversation.id, e_f)
                    
                    self.env['mail.activity'].search([
                        ('res_model', '=', self._name),
                        ('res_id', '=', conv_to_merge.id)
                    ]).write({'res_id': master_conversation.id, 'res_model': self._name})

                # --- 5. Lưu log về việc merge vào master conversation ---
                merged_conv_info_for_log = []
                for conv in conversations_to_merge_records:
                    details = [f"Odoo ID {conv.id}"]
                    if conv.name: 
                        details.append(f"Name: '{conv.name}'")
                    cw_ids_log = []
                    if conv.chatwoot_conversation_id:
                        cw_ids_log.append(str(conv.chatwoot_conversation_id))
                    # Lấy thêm từ related_chatwoot_conversations nếu có
                    if isinstance(conv.related_chatwoot_conversations, list):
                         for item in conv.related_chatwoot_conversations:
                            if isinstance(item, dict) and item.get('id') and str(item.get('id')) not in cw_ids_log:
                                cw_ids_log.append(str(item.get('id')))
                    if cw_ids_log:
                        details.append(f"Chatwoot ID(s): {', '.join(cw_ids_log)}")
                    merged_conv_info_for_log.append(" | ".join(details))
                
                log_message_body = _("The following conversations have been merged into this one:\n- %s") % '\n- '.join(merged_conv_info_for_log)
                master_conversation.message_post(body=log_message_body, message_type='notification', subtype_xmlid='mail.mt_note')
                
                # --- 6. Archive các cuộc hội thoại phụ ---
                if conversations_to_merge_records:
                    _logger.info(">>> MERGE: Archiving %s secondary conversations: %s...", len(conversations_to_merge_records), conversations_to_merge_records.ids)
                    conversations_to_merge_records.write({'active': False})

            except Exception as e:
                self.env.cr.rollback()
                _logger.error(">>> MERGE: Error during merge process: %s", e, exc_info=True)
                return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                    'title': _('Merge Error'),
                    'message': _("An error occurred: %s") % e,
                    'type': 'danger', 'sticky': True,
                }}

        _logger.info(">>> MERGE: Action completed for master Odoo ID %s.", master_conversation.id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Merge Successful"),
                'message': _("%s conversation(s) merged into '%s'.") % (len(conversations_to_merge_records), master_conversation.display_name),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        """
        Override để bắt tin nhắn do người dùng Odoo gửi từ chatter
        và gửi nó tới Chatwoot, đồng thời tạo bản ghi chatopia.message.
        """
        # Gọi hàm message_post gốc để tạo mail.message
        # self.with_context(mail_post_autofollow=True) có thể không cần thiết nếu bạn không muốn ép autofollow
        # Hoặc nếu bạn muốn kiểm soát followers một cách khác.
        # Mặc định, message_post đã xử lý followers.
        mail_message = super(ChatConversation, self).message_post(**kwargs) # Bỏ with_context ở đây nếu không chắc chắn
        
        is_comment = kwargs.get('message_type') == 'comment'
        # subtype_id có thể tin cậy hơn subtype_xmlid nếu subtype_xmlid không được truyền tường minh
        is_internal_note = mail_message.subtype_id and mail_message.subtype_id.internal # Cách kiểm tra note nội bộ tốt hơn

        # Kiểm tra người gửi: mail_message.author_id là partner của người gửi.
        # self.env.user.partner_id là partner của người dùng Odoo hiện tại đang thực hiện hành động.
        # Điều kiện này đúng khi người dùng hiện tại chính là người tạo ra mail.message.
        # Hoặc nếu mail_message được tạo bởi một user khác nhưng bạn vẫn muốn gửi (ví dụ: gửi thay mặt) thì logic sẽ khác.
        # Hiện tại, giả sử chỉ gửi nếu người dùng hiện tại là tác giả.
        is_odoo_user_initiated = mail_message.author_id and mail_message.author_id == self.env.user.partner_id

        if mail_message and is_odoo_user_initiated and \
           is_comment and not is_internal_note and \
           not self.env.context.get('from_chatwoot_sync'): # Cờ quan trọng để tránh vòng lặp
            
            _logger.info(f"Odoo user initiated message (mail.message ID: {mail_message.id}) in Odoo Conversation {self.id}. Preparing to send to Chatwoot.")
            try:
                message_body_text = tools.html2plaintext(mail_message.body).strip()
                if not message_body_text:
                    _logger.info(f"Message body is empty for mail.message {mail_message.id}, not sending to Chatwoot.")
                    return mail_message # Vẫn trả về mail_message đã tạo

                # Gọi _send_content_to_chatwoot.
                # Hàm này đã được sửa để trả về response_data (dict) hoặc False.
                # Nó cũng đã có default cho các tham số message_type, private, content_attributes
                chatwoot_response_data = self._send_content_to_chatwoot(
                    content=message_body_text,
                    # target_chatwoot_conv_id mặc định sẽ là self.chatwoot_conversation_id
                )

                if chatwoot_response_data and isinstance(chatwoot_response_data, dict):
                    _logger.info(f"Successfully sent message to Chatwoot. Response: {chatwoot_response_data.get('id')}")
                    
                    # Tạo bản ghi chatopia.message để lưu lại tin nhắn đã gửi từ Odoo
                    chatwoot_msg_id_from_response = chatwoot_response_data.get('id')
                    chatwoot_created_at_str = chatwoot_response_data.get('created_at') # ISO 8601 string
                    
                    odoo_created_at_for_chatopia_msg = None
                    if chatwoot_created_at_str:
                        try:
                            # Parse ISO string thành "YYYY-MM-DD HH:MM:SS"
                            odoo_created_at_for_chatopia_msg = chatwoot_created_at_str.split('.')[0].replace('Z', '').replace('T', ' ')
                        except Exception as e_parse:
                            _logger.warning(f"Could not parse created_at ('{chatwoot_created_at_str}') from Chatwoot response: {e_parse}. Using current time for chatopia.message.")
                            odoo_created_at_for_chatopia_msg = fields.Datetime.now() # Fallback
                    else:
                        odoo_created_at_for_chatopia_msg = fields.Datetime.now() # Fallback

                    # Lấy ID Chatwoot của conversation mà tin nhắn đã được gửi tới
                    # Hàm _send_content_to_chatwoot dùng self.chatwoot_conversation_id nếu target_chatwoot_conv_id không được truyền.
                    # Hoặc nếu bạn đã sửa _send_content_to_chatwoot để nó trả về target_id đã dùng trong response_data thì càng tốt.
                    # Hiện tại, giả sử nó gửi đến self.chatwoot_conversation_id
                    target_cw_conv_id_used = chatwoot_response_data.get('conversation_id') or self.chatwoot_conversation_id

                    chatopia_message_vals = {
                        'conversation_id': self.id,
                        'chatwoot_message_id': chatwoot_msg_id_from_response, # ID của message từ Chatwoot
                        'chatwoot_conversation_id': target_cw_conv_id_used, # ID Chatwoot của conversation
                        'content': message_body_text, # Nội dung đã gửi
                        'sender': self.env.user.partner_id.name or "Odoo User", # Người gửi là user Odoo
                        'message_type': 'admin', # Hoặc 'outgoing', tùy theo định nghĩa selection của bạn
                        'created_at': odoo_created_at_for_chatopia_msg,
                        'is_read': True, # Tin nhắn từ Odoo gửi đi thì coi như đã đọc bởi người gửi
                        'mail_message_id_link': mail_message.id, # Liên kết với mail.message vừa tạo
                        # Các trường related như inbox_name, inbox_names sẽ tự điền từ conversation_id
                    }
                    self.env['chatopia.message'].create(chatopia_message_vals)
                    _logger.info(f"Created chatopia.message record for Odoo-sent message (mail.message ID {mail_message.id}).")
                else:
                    # _send_content_to_chatwoot trả về False hoặc không phải dict
                    _logger.error(f"Failed to send Odoo message {mail_message.id} to Chatwoot (no valid response data) for Odoo Conversation {self.id}.")
                    # Có thể post tin nhắn lỗi vào chatter để người dùng biết
                    self.message_post(
                        body=_("Error: This message could not be delivered to Chatwoot. Please check system logs or contact an administrator."),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note', # Tin nhắn hệ thống (note)
                        author_id=False # Gửi như hệ thống
                    )

            except Exception as e:
                _logger.error(f"Error processing Odoo message {mail_message.id} for Chatwoot delivery (conv {self.id}): {e}", exc_info=True)
                # Tương tự, có thể post lỗi vào chatter
        
        elif is_internal_note:
            _logger.info(f"Internal note (mail.message {mail_message.id}) posted for Odoo Conversation {self.id}. Not sending to Chatwoot.")
        # else:
            # _logger.debug(f"Message (mail.message ID: {mail_message.id}) for Odoo Conversation {self.id} not sent to Chatwoot. Conditions not met. Author: {mail_message.author_id}, Type: {kwargs.get('message_type')}, Context: {self.env.context}")
        
        return mail_message

    def _send_content_to_chatwoot(self, content, target_chatwoot_conv_id=None, message_type="outgoing", private=False, content_attributes=None):
        """
        Hàm riêng để gửi nội dung đến Chatwoot.
        target_chatwoot_conv_id: ID Chatwoot cụ thể để gửi đến. Nếu None, dùng self.chatwoot_conversation_id.
        Trả về dữ liệu JSON của tin nhắn được tạo bởi Chatwoot nếu thành công, ngược lại là False.
        """
        self.ensure_one()
        if not content:
            _logger.warning("No content to send to Chatwoot.")
            return False

        # Xác định ID Chatwoot Conversation để sử dụng
        chatwoot_conv_id_to_use = target_chatwoot_conv_id or self.chatwoot_conversation_id

        if not chatwoot_conv_id_to_use:
            _logger.error(f"No target Chatwoot Conversation ID specified or available for Chatopia Conversation {self.id}. Cannot send message.")
            return False

        config_params = self.env['ir.config_parameter'].sudo()
        chatwoot_base_url = config_params.get_param('chatwoot.base_url', default="https://lvshipper.io.vn")
        chatwoot_account_id = config_params.get_param('chatwoot.account_id', default="1")
        chatwoot_api_token = config_params.get_param('chatwoot.api_access_token', default="gg5vjCgX57BDKoCTzSZfkEe4")

        if not all([chatwoot_base_url, chatwoot_account_id, chatwoot_api_token]):
            _logger.error("Chatwoot integration parameters (URL, Account ID, or Token) not fully configured in System Parameters.")
            return False

        chatwoot_url = f"{chatwoot_base_url.strip('/')}/api/v1/accounts/{chatwoot_account_id}/conversations/{chatwoot_conv_id_to_use}/messages"

        payload_data = { # Đổi tên biến để tránh nhầm lẫn với biến payload trong global scope của server action
            "content": content,
            "message_type": message_type,
            "private": private,
        }
        if content_attributes:
            payload_data["content_attributes"] = content_attributes

        headers = {
            "Content-Type": "application/json",
            "api_access_token": chatwoot_api_token
        }

        _logger.info(f"Sending message to Chatwoot. URL: {chatwoot_url}, Target Chatwoot Conv ID: {chatwoot_conv_id_to_use}, Odoo Conv ID: {self.id}")
        
        try:
            response = requests.post(chatwoot_url, data=json.dumps(payload_data), headers=headers, timeout=15)
            response.raise_for_status() 
            response_data = response.json()
            _logger.info(f"Message sent successfully to Chatwoot for Odoo conv {self.id}. Chatwoot Msg ID: {response_data.get('id')} (sent to Chatwoot Conv ID: {chatwoot_conv_id_to_use})")
            return response_data
        except requests.exceptions.HTTPError as e:
            _logger.error(f"Chatwoot API HTTP Error for Odoo conv {self.id} (target CW ID {chatwoot_conv_id_to_use}): {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            _logger.error(f"Chatwoot API Request Error for Odoo conv {self.id} (target CW ID {chatwoot_conv_id_to_use}): {e}")
        except json.JSONDecodeError as e:
            _logger.error(f"Chatwoot API JSON Decode Error for Odoo conv {self.id} (target CW ID {chatwoot_conv_id_to_use}). Response: {response.text if 'response' in locals() else 'N/A'}. Error: {e}")
        except Exception as e:
            _logger.error(f"Unexpected error sending message to Chatwoot for Odoo conv {self.id} (target CW ID {chatwoot_conv_id_to_use}): {e}", exc_info=True)
        
        return False

    def send_message_custom_button(self):
        self.ensure_one()
        if not self.message_content_to_send:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Missing Content'),
                'message': _('Please enter message content to send.'),
                'type': 'warning', 'sticky': False,
            }}

        # Danh sách cuối cùng các chi tiết để hiển thị
        # Mỗi item: {'cw_id': <int>, 'inbox_id_display': <int_or_str_None>, 'inbox_name_display': <str>}
        display_details = [] # Giả sử final_unique_id_details đã được tạo đúng
        seen_display_cw_ids = set()

        if isinstance(self.related_chatwoot_conversations, list):
            for conv_detail in self.related_chatwoot_conversations:
                if isinstance(conv_detail, dict) and conv_detail.get('id'):
                    cw_id = conv_detail.get('id')
                    if cw_id not in seen_display_cw_ids:
                        inbox_id = conv_detail.get('inbox_id')
                        inbox_name = conv_detail.get('inbox_name')
                        if not inbox_name and inbox_id:
                            inbox_name = self._get_inbox_name_by_id(inbox_id) # Giả sử hàm này tồn tại
                        
                        display_details.append({
                            'cw_id': cw_id,
                            'inbox_id_display': inbox_id if inbox_id else _("N/A"),
                            'inbox_name_display': inbox_name or _("Unknown Inbox")
                        })
                        seen_display_cw_ids.add(cw_id)

        if self.chatwoot_conversation_id and self.chatwoot_conversation_id not in seen_display_cw_ids:
            main_inbox_id = self.x_chatwoot_inbox_id
            main_inbox_name = self.inbox_name
            if not main_inbox_name and main_inbox_id:
                 main_inbox_name = self._get_inbox_name_by_id(main_inbox_id)
            display_details.append({
                'cw_id': self.chatwoot_conversation_id,
                'inbox_id_display': main_inbox_id if main_inbox_id else _("N/A"),
                'inbox_name_display': main_inbox_name or _("Primary Inbox")
            })

        if display_details:
            display_details.sort(key=lambda x: x['cw_id'])

        if not display_details:
            # ... (notification không có ID) ...
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('No Target Available'),
                'message': _('No valid Chatwoot Conversation IDs found for this Odoo conversation.'),
                'type': 'warning', 'sticky': False,
            }}

        # Tạo chuỗi TEXT THUẦN hiển thị thông tin cho wizard
        info_text_parts = []
        info_text_parts.append(_("Available targets to send message to:")) # Không có <p> hay <strong>
        
        for detail in display_details:
            # Mỗi mục là một dòng, sử dụng ký tự xuống dòng \n
            # Bỏ các thẻ <b>, <i>, <ul>, <li>
            info_text_parts.append(
                "- %s: %s (%s: %s, %s: %s)" % 
                (
                    _("Chatwoot ID"), detail['cw_id'], 
                    _("Inbox ID"), detail['inbox_id_display'],
                    _("Inbox Name"), detail['inbox_name_display']
                )
            )
        
        available_ids_info_text = "\n".join(info_text_parts) # Nối bằng \n
        
        # ... (Xác định default_target_id_to_input như trước) ...
        default_target_id_to_input = None
        if display_details:
            primary_cw_id_for_default = self.chatwoot_conversation_id
            default_item = next((item for item in display_details if item['cw_id'] == primary_cw_id_for_default), None)
            if default_item:
                default_target_id_to_input = default_item['cw_id']
            else:
                default_target_id_to_input = display_details[0]['cw_id']
        
        ctx = {
            'default_conversation_odoo_id': self.id,
            'default_message_content_display': self.message_content_to_send,
            'default_available_ids_info': available_ids_info_text, # Truyền chuỗi TEXT
            'default_target_chatwoot_conv_id_input': default_target_id_to_input
        }
        _logger.info(">>> Opening manual input wizard with PLAIN TEXT context: %s", ctx)

        return {
            'name': _('Send to Specific Chatwoot Conversation'),
            'type': 'ir.actions.act_window',
            'res_model': 'chatopia.select.chatwoot.conversation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    # Hàm mới để xử lý sau khi wizard chọn xong
    def process_send_to_selected_chatwoot_id(self, content, target_chatwoot_conv_id):
        """
        Được gọi từ wizard để thực sự gửi tin nhắn và tạo các bản ghi Odoo.
        """
        self.ensure_one()
        chatwoot_response_data = self._send_content_to_chatwoot(content, target_chatwoot_conv_id=target_chatwoot_conv_id)

        if chatwoot_response_data and isinstance(chatwoot_response_data, dict):
            posted_mail_message = self.with_context(
                from_chatwoot_sync=True,
                mail_create_nosubscribe=True,
                mail_post_autofollow=False 
            ).message_post(
                body=content,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=self.env.user.partner_id.id
            )

            chatwoot_msg_id_from_response = chatwoot_response_data.get('id')
            chatwoot_created_at_str = chatwoot_response_data.get('created_at')
            
            odoo_created_at = None
            if chatwoot_created_at_str:
                try:
                    odoo_created_at = chatwoot_created_at_str.split('.')[0].replace('Z', '').replace('T', ' ')
                except:
                    odoo_created_at = None 

            chatopia_message_vals = {
                'conversation_id': self.id,
                'chatwoot_message_id': chatwoot_msg_id_from_response,
                # Lưu ID Chatwoot của conversation mà tin nhắn này thực sự được gửi tới
                'chatwoot_conversation_id': target_chatwoot_conv_id, 
                'content': content,
                'sender': self.env.user.partner_id.name or "Odoo User",
                'message_type': 'admin',
                'is_read': True,
                'mail_message_id_link': posted_mail_message.id if posted_mail_message else False,
            }
            if odoo_created_at:
                chatopia_message_vals['created_at'] = odoo_created_at
            
            self.env['chatopia.message'].create(chatopia_message_vals)
            
            # Xóa nội dung message_content_to_send nếu tin nhắn này bắt nguồn từ đó
            if self.message_content_to_send == content:
                 self.message_content_to_send = False
            
            _logger.info(f"Wizard Send: Message sent to Chatwoot (CW ID: {chatwoot_msg_id_from_response} to target CW Conv ID {target_chatwoot_conv_id}), posted to Odoo chatter for conv {self.id}")
            return True # Thành công
        else:
            _logger.error(f"Wizard Send: Failed to send message to Chatwoot (target CW Conv ID {target_chatwoot_conv_id}) for conversation {self.id}.")
            return False # Thất bại

    # --- Xử lý tin nhắn ĐẾN từ Chatwoot (ví dụ: qua webhook) ---
    @api.model
    def receive_message_from_chatwoot(self, chatwoot_payload):
        """
        Hàm mẫu để xử lý payload từ webhook của Chatwoot.
        Bạn cần gọi hàm này từ controller của webhook.
        """
        _logger.info(f"Received message from Chatwoot: {json.dumps(chatwoot_payload)}")

        # ---- Trích xuất thông tin từ Chatwoot Payload ----
        # Đây là ví dụ, bạn cần điều chỉnh dựa trên cấu trúc payload thực tế của Chatwoot
        chatwoot_conv_id = chatwoot_payload.get('conversation', {}).get('id')
        chatwoot_msg_id = chatwoot_payload.get('id')
        content = chatwoot_payload.get('content')
        message_type = chatwoot_payload.get('message_type') # "incoming", "outgoing", "template"
        is_private = chatwoot_payload.get('private', False) # Tin nhắn nội bộ trong Chatwoot
        sender_info = chatwoot_payload.get('sender') # Object chứa thông tin người gửi (contact hoặc agent)
        # created_at_timestamp = chatwoot_payload.get('created_at') # Timestamp, ví dụ: 1609459200

        if not chatwoot_conv_id or not content:
            _logger.warning("Chatwoot payload missing conversation ID or content. Skipping.")
            return {'status': 'error', 'message': 'Missing conversation ID or content'}

        if is_private:
            _logger.info(f"Skipping private Chatwoot message {chatwoot_msg_id} for conversation {chatwoot_conv_id}.")
            return {'status': 'ok', 'message': 'Private message skipped'}

        # ---- Tìm hoặc tạo Conversation trong Odoo ----
        conversation = self.search([('chatwoot_conversation_id', '=', chatwoot_conv_id)], limit=1)
        if not conversation:
            # Logic tạo conversation mới nếu chưa có
            # Bạn cần thêm thông tin như inbox_name, sender_name, contact_id từ payload
            # Ví dụ:
            # contact_payload = chatwoot_payload.get('meta', {}).get('sender')
            # contact_name = contact_payload.get('name')
            # contact_email = contact_payload.get('email')
            # partner = self.env['res.partner'].search([('email', '=', contact_email)], limit=1)
            # if not partner and contact_email:
            #     partner = self.env['res.partner'].create({'name': contact_name, 'email': contact_email})
            #
            # conversation = self.create({
            #     'name': f"Chatwoot Conv {chatwoot_conv_id}", # Tên tạm thời
            #     'chatwoot_conversation_id': chatwoot_conv_id,
            #     'contact_id': partner.id if partner else False,
            #     # ... các trường khác ...
            # })
            _logger.warning(f"Conversation with Chatwoot ID {chatwoot_conv_id} not found in Odoo. Message {chatwoot_msg_id} might be lost if creation logic is not robust.")
            # For now, we'll skip if conversation doesn't exist to prevent errors.
            # In a real scenario, you'd create it.
            return {'status': 'error', 'message': f'Conversation {chatwoot_conv_id} not found'}


        # ---- Xử lý người gửi (Sender) ----
        author_id = False # res.partner ID của người gửi
        email_from = self.env.user.company_id.email or "noreply@example.com" # Email mặc định
        author_name = "Chatwoot User"

        if sender_info: # Nếu là agent gửi từ Chatwoot hoặc contact
            sender_type = sender_info.get('type') # 'contact', 'agent_bot', 'user' (agent)
            author_name = sender_info.get('name', author_name)
            sender_email = sender_info.get('email')

            if sender_email:
                email_from = sender_email
                partner = self.env['res.partner'].search([('email', '=ilike', sender_email)], limit=1)
                if not partner:
                    # Tạo partner mới nếu không tìm thấy
                    partner_vals = {'name': author_name, 'email': sender_email}
                    # Nếu là contact, có thể thêm vào contact_ids của conversation
                    if sender_type == 'contact' and conversation.contact_id and conversation.contact_id.email == sender_email:
                        partner = conversation.contact_id # Nếu contact chính là người gửi
                    elif sender_type == 'contact': # Nếu là contact khác, hoặc contact_id chưa có
                        # Cân nhắc có nên tự động tạo partner cho mỗi contact lạ không
                        # partner = self.env['res.partner'].sudo().create(partner_vals)
                        _logger.info(f"New contact from Chatwoot: {author_name} <{sender_email}>. Consider auto-creating res.partner.")
                        # Hiện tại không tự tạo partner lạ để tránh rác, trừ khi đã có trong hệ thống
                        # Partner này có thể là 1 User Odoo (agent)
                        user_agent = self.env['res.users'].search([('partner_id.email', '=ilike', sender_email)], limit=1)
                        if user_agent:
                            partner = user_agent.partner_id

                if partner:
                    author_id = partner.id
            else: # Không có email, thử tìm user/partner bằng tên (ít tin cậy hơn)
                # Nếu là agent, tên có thể trùng với user Odoo
                if sender_type == 'user': # Agent
                    user_agent = self.env['res.users'].search([('name', '=', author_name)], limit=1)
                    if user_agent:
                        author_id = user_agent.partner_id.id
        
        # Format email_from cho mail.message
        formatted_email_from = tools.formataddr((author_name, email_from))

        # ---- Post tin nhắn vào chatter của Odoo ----
        # Sử dụng context để hàm message_post không cố gắng gửi lại tin nhắn này cho Chatwoot
        try:
            posted_message = conversation.with_context(from_chatwoot_sync=True).message_post(
                body=content,
                author_id=author_id, # Partner ID của người gửi (nếu có)
                email_from=formatted_email_from,
                message_type='comment', # Quan trọng: để hiển thị như tin nhắn chat
                subtype_xmlid='mail.mt_comment', # Subtype chuẩn cho comment
                # attachment_ids=... # Xử lý attachments nếu có
                # message_id= ... # Nếu bạn muốn set Message-ID header
                # subject= ... # Nếu cần
            )
            _logger.info(f"Message from Chatwoot (ID: {chatwoot_msg_id}) posted to Odoo conversation {conversation.id} as mail.message {posted_message.id}")

            # (Tùy chọn) Tạo bản ghi chatopia.message để lưu trữ thông tin gốc từ Chatwoot
            self.env['chatopia.message'].create({
                'conversation_id': conversation.id,
                'chatwoot_message_id': chatwoot_msg_id,
                'inbox_id': chatwoot_payload.get('inbox',{}).get('id'),
                'chatwoot_conversation_id': chatwoot_conv_id,
                'sender': author_name,
                'content': content,
                'message_type': 'user' if message_type == 'incoming' else 'admin', # Hoặc dựa trên sender_type
                'created_at': fields.Datetime.now(), # Hoặc chuyển đổi từ created_at_timestamp
                'mail_message_id_link': posted_message.id # Liên kết với mail.message
            })
            # Cập nhật last message time/content trên conversation (sẽ tự tính lại do compute)
            # conversation._compute_last_message_display_fields() # Không cần gọi trực tiếp
            return {'status': 'ok', 'message': f'Message {chatwoot_msg_id} processed'}

        except Exception as e:
            _logger.error(f"Error posting Chatwoot message {chatwoot_msg_id} to Odoo conversation {conversation.id}: {e}", exc_info=True)
            return {'status': 'error', 'message': f'Error processing message: {e}'}

    # Hàm _extract_zalo_user_id_from_email không thay đổi
    def _extract_zalo_user_id_from_email(self):
        self.ensure_one()
        if not self.contact_id:
            _logger.warning(f"Cuộc hội thoại ID {self.id} không có liên kết Contact.")
            return None, _("Cuộc hội thoại này chưa được liên kết với một Liên hệ (Contact).")

        contact_email = self.contact_id.email
        if not contact_email:
            _logger.warning(f"Contact ID {self.contact_id.id} không có địa chỉ email.")
            return None, _("Liên hệ '%s' không có địa chỉ email được thiết lập.") % self.contact_id.display_name

        email_parts = contact_email.split('@gmail.com')
        if len(email_parts) == 2 and email_parts[1] == '' and email_parts[0]:
            zalo_user_id = email_parts[0]
            if re.match(r'^\d+$', zalo_user_id):
                _logger.info(f"Trích xuất thành công Zalo User ID: {zalo_user_id} từ email: {contact_email}")
                return zalo_user_id, None
            else:
                _logger.warning(
                    f"Phần trước '@gmail.com' trong email '{contact_email}' không phải là ID hợp lệ (chỉ chứa số).")
                return None, _("Định dạng email của liên hệ '%s' không đúng chuẩn để lấy Zalo User ID (phần trước @gmail.com phải là số). Email hiện tại: %s") % (
                self.contact_id.display_name, contact_email)
        else:
            _logger.warning(f"Email '{contact_email}' của Contact ID {self.contact_id.id} không đúng định dạng '[zalo_user_id]@gmail.com'.")
            return None, _("Email của liên hệ '%s' không đúng định dạng '[zalo_user_id]@gmail.com'. Email hiện tại: %s") % (
            self.contact_id.display_name, contact_email)

    # Hàm send_message_to_zalo không thay đổi logic cốt lõi, chỉ cần đảm bảo message_content lấy từ đâu
    # Hiện tại nó đang dùng self.message_content. Nếu bạn muốn gửi từ chatter, logic gọi sẽ khác.
    # ... (Giữ nguyên hàm send_message_to_zalo)
        
        # def send_message_to_zalo(self):
    #     self.ensure_one()

    #     if not self.message_content:
    #         raise UserError(_("Vui lòng nhập nội dung tin nhắn trước khi gửi."))

    #     recipient_zalo_id, error_message = self._extract_zalo_user_id_from_email()

    #     if not recipient_zalo_id:
    #         raise UserError(error_message)

    #     content_to_send = self.message_content

    #     zalo_api_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    #     zalo_access_token = "rz7BCcPlwqlJrSCwP6ZbITJLpJvv1BSEm_N342Ski3hXtf8v30R7E-N2XJCv0-yJZEJC1dW2j3MUyEekAa6N7D6dipOvUk0uyhQX0ILurtdAcwHx7s3dQSc4lrivMkGfqRsP1mrqoZpjoPy5NWV0CUxWenbLHSGNffgr2MjOoWcgiOr-6stP3wYqXW061D9rj-UjUtK5a42K_x5RHoUHOht2y6b92B9PWzJ9KdaJh7wSxlHPHW-sQhpWyMrlBTTjtjtp7nOHbIVWpyDHEGY_H-3KvarIBeP3a8lcOo1Elqxxy9r1JZ_iSlxwltG_5lTdxz-Z50PlqIF1rF8w1Mc4AS2nvY0aSfiBbgtk6LONdG2QgxiCStJZFAgoWJ9HVjKvexUC7aTqrZQGdueMS7drFPs_WKv6VU5kWuWGGM1tuqS"

    #     if not zalo_access_token:
    #         _logger.error("Thiếu Zalo Access Token trong cấu hình hệ thống.")
    #         raise UserError(_("Chưa cấu hình Zalo Access Token trong Hệ thống > Thông số kỹ thuật > Tham số hệ thống (vd: zalo.oa.access_token)."))

    #     payload = {
    #         "recipient": {
    #             "user_id": recipient_zalo_id
    #         },
    #         "message": {
    #             "text": content_to_send
    #         }
    #     }

    #     headers = {
    #         "Content-Type": "application/json",
    #         "access_token": zalo_access_token
    #     }

    #     _logger.info(f"Chuẩn bị gửi tin nhắn Zalo đến User ID: {recipient_zalo_id} (trích xuất từ contact {self.contact_id.id})")
    #     _logger.debug(f"Zalo Payload: {json.dumps(payload)}")

    #     try:
    #         _logger.info(f"Đang gửi request đến Zalo API: {zalo_api_url}")
    #         response = requests.post(zalo_api_url, data=json.dumps(payload), headers=headers, timeout=15)
    #         response.raise_for_status()

    #         response_data = response.json()
    #         _logger.info("Gửi request Zalo thành công.")
    #         _logger.info(f"Zalo Response Status Code: {response.status_code}")
    #         _logger.info(f"Zalo Response Body: {response_data}")

    #         zalo_error_code = response_data.get('error')
    #         zalo_error_message = response_data.get('message', '')
    #         if zalo_error_code is not None and zalo_error_code != 0:
    #             _logger.error(f"Zalo API trả về lỗi: Code={zalo_error_code}, Message='{zalo_error_message}' cho User ID: {recipient_zalo_id}")
    #             error_detail = f" (User ID: {recipient_zalo_id}, Lỗi Zalo: {zalo_error_message})"
    #             raise UserError(_("Zalo API báo lỗi khi gửi tin nhắn: %s%s") % (zalo_error_message, error_detail))

    #         self.env['chatopia.message'].create({
    #             'conversation_id': self.id,
    #             'content': content_to_send,
    #             'sender': self.env.user.name or 'Odoo User',
    #             'message_type': 'admin',
    #             'created_at': fields.Datetime.now(),
    #         })

    #         self.message_content = False
    #         _logger.info(f"Đã gửi tin nhắn thành công đến Zalo User ID: {recipient_zalo_id}")

    #         return True

    #     except requests.exceptions.Timeout as e:
    #         _logger.error(f"Lỗi gửi tin nhắn Zalo (Timeout) đến User ID {recipient_zalo_id}: {e}")
    #         raise UserError(_("Gửi tin nhắn tới Zalo thất bại do hết thời gian chờ. Vui lòng thử lại."))
    #     except requests.exceptions.HTTPError as e:
    #         error_details = e.response.text
    #         status_code = e.response.status_code
    #         try:
    #             error_json = e.response.json()
    #             error_details = f"Code: {error_json.get('error', 'N/A')}, Message: {error_json.get('message', e.response.text)}"
    #         except json.JSONDecodeError:
    #             pass
    #         _logger.error(f"Lỗi gửi tin nhắn Zalo (HTTP Error {status_code}) đến User ID {recipient_zalo_id}: {error_details}")
    #         raise UserError(_("Gửi tin nhắn tới Zalo thất bại. Lỗi HTTP %s: %s (Kiểm tra Access Token hoặc User ID có thể không hợp lệ/không tồn tại)") % (status_code, error_details))
    #     except requests.exceptions.RequestException as e:
    #         _logger.error(f"Lỗi kết nối khi gửi tin nhắn Zalo đến User ID {recipient_zalo_id}: {e}")
    #         raise UserError(_("Gửi tin nhắn tới Zalo thất bại. Không thể kết nối tới Zalo API: %s") % e)
    #     except Exception as e:
    #         _logger.exception(f"Lỗi không xác định khi gửi tin nhắn Zalo đến User ID {recipient_zalo_id}:")
    #         raise UserError(_("Đã xảy ra lỗi không mong muốn khi gửi tin nhắn Zalo: %s") % e)
    
    def action_toggle_starred(self):
        for record in self:
            record.is_starred = not record.is_starred
        return True # Trả về True hoặc một action để refresh view nếu cần

    # Hàm để đánh dấu tất cả tin nhắn trong các cuộc trò chuyện đã chọn là đã đọc
    # Nút này thường nằm trong menu "Action" hoặc header của view
    @api.model
    def action_mark_as_read(self, conversation_ids):
        """Marks messages within specified conversations as read for the current user."""
        if not conversation_ids:
            return True
        
        conversations = self.browse(conversation_ids)
        # Tìm các tin nhắn mail.message liên quan đến các cuộc trò chuyện này và cần hành động (chưa đọc)
        messages_to_mark = self.env['mail.message'].search([
            ('model', '=', self._name),
            ('res_id', 'in', conversations.ids),
            ('needaction', '=', True) # 'needaction' = True nghĩa là chưa đọc đối với người dùng hiện tại
        ])
        if messages_to_mark:
            messages_to_mark.set_message_done() # Đánh dấu là đã đọc cho người dùng hiện tại
        return True

    # Hàm này có thể được gọi từ một nút "Mark all read" trên thanh công cụ (ví dụ: server action)
    # để đánh dấu tất cả các mục phù hợp với bộ lọc hiện tại là đã đọc.
    @api.model
    def mark_all_conversations_in_view_as_read(self, domain=None):
        """
        Marks all conversations matching the domain as read for the current user.
        This is a placeholder for a more complex server action that might take the current view's domain.
        """
        if domain is None:
            domain = []
        
        # Chỉ xử lý các cuộc trò chuyện có tin nhắn chưa đọc
        conversations_with_unread = self.search(domain + [('message_needaction', '=', True)])
        if conversations_with_unread:
            self.action_mark_as_read(conversations_with_unread.ids)
        return True