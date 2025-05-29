from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
import re

_logger = logging.getLogger(__name__)

class ChatConversation(models.Model):
    _name = 'chatopia.conversation'
    _description = 'Chat Conversation'
    _order = 'last_message_time desc, id desc'

    name = fields.Char(string="Conversation Name")
    chatwoot_conversation_id = fields.Integer(string="Chatwoot Conversation ID")
    inbox_name = fields.Char(string="Inbox Name")
    sender_name = fields.Char(string="Sender Name")
    inbox_names = fields.Json(string="Inbox Names")
    sender_names = fields.Json(string="Sender Names")
    contact_id = fields.Many2one('res.partner', string="Contact", required=True)
    contact_ids = fields.Many2many(
        'res.partner',
        'chatopia_conversation_res_partner_rel',
        'conversation_id',
        'partner_id',
        string="Contacts"
    )
    message_ids = fields.One2many('chatopia.message', 'conversation_id', string="Messages")
    message_content = fields.Text(string="Message Content")
    x_chatwoot_contact_id = fields.Char(string="Chatwoot Contact ID")
    x_chatwoot_inbox_id = fields.Integer(string="Chatwoot Inbox ID")
    last_message_content = fields.Text(string="Last Message Content")
    last_message_time = fields.Datetime(string="Last Message Time")
    avatar = fields.Binary(string="Avatar")
    
    inbox_names_display = fields.Char(string="Inbox Names (Display)", compute="_compute_inbox_names_display")
    sender_names_display = fields.Char(string="Sender Names (Display)", compute="_compute_sender_names_display")

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
    def action_merge_selected(self):
        """ Gộp các cuộc hội thoại đã chọn. """
        # 'self' ở đây là recordset chứa các bản ghi chatopia.conversation mà người dùng đã chọn

        _logger.info(">>> Starting merge action. Selected %s conversations.", len(self))

        if len(self) < 2:
            _logger.warning(">>> Less than 2 conversations selected.")
            raise UserError(_("Vui lòng chọn ít nhất hai cuộc hội thoại để gộp."))

        # Chọn bản ghi chính (master record) - Ở đây chọn bản ghi đầu tiên trong recordset được chọn
        # Bạn có thể thay đổi logic chọn master nếu cần (ví dụ: bản ghi cũ nhất, mới nhất, v.v.)
        master_conversation = self[0]
        # Các bản ghi còn lại là những bản ghi sẽ bị gộp và xóa
        conversations_to_merge = self[1:]

        _logger.info(">>> Master conversation ID: %s", master_conversation.id)
        _logger.info(">>> Conversations to merge IDs: %s", conversations_to_merge.ids)

        # 1. Thu thập TẤT CẢ tin nhắn từ TẤT CẢ các cuộc hội thoại đã chọn (master + to_merge)
        # Sử dụng self.mapped('message_ids') trên recordset BAN ĐẦU (self)
        all_selected_messages = self.mapped('message_ids')
        _logger.info(">>> Number of messages found in all selected conversations: %s", len(all_selected_messages))

        if all_selected_messages:
            _logger.info(">>> Relinking all selected messages to master conversation %s...", master_conversation.id)
            try:
                # Cập nhật conversation_id cho TẤT CẢ tin nhắn này để trỏ về bản ghi chính
                all_selected_messages.write({'conversation_id': master_conversation.id})
                _logger.info(">>> All selected messages relinked successfully.")
            except Exception as e:
                _logger.error(">>> Error relinking messages: %s", e, exc_info=True)
                # Nâng ngoại lệ với thông báo thân thiện hơn cho người dùng
                raise UserError(_("Đã xảy ra lỗi khi gộp tin nhắn: %s") % e)
        else:
             _logger.warning(">>> No messages found in any of the selected conversations.")


        # 2. Cập nhật các trường dẫn xuất (như last_message_content, last_message_time) trên bản ghi chính
        # Sau khi relink, master_conversation.message_ids bây giờ chứa TẤT CẢ các tin nhắn đã gộp
        # Chúng ta cần tìm tin nhắn mới nhất từ TẬP HỢP ĐÃ GỘP NÀY
        # Sử dụng search với order và limit=1 để lấy hiệu quả chỉ 1 tin nhắn mới nhất
        _logger.info(">>> Searching for the latest message for master conversation %s...", master_conversation.id)
        try:
            latest_message_recordset = self.env['chatopia.message'].search(
                [('conversation_id', '=', master_conversation.id)], # Tìm tin nhắn của master_conversation (sau khi relink đã bao gồm tất cả)
                order='created_at desc, id desc', # Sắp xếp giảm dần theo thời gian để tin nhắn mới nhất lên đầu
                limit=1 # Chỉ lấy 1 bản ghi
            )

            if latest_message_recordset:
                # latest_message_recordset là một recordset chứa 1 bản ghi (hoặc rỗng nếu không có tin nhắn)
                latest_message = latest_message_recordset[0] # Lấy bản ghi duy nhất từ recordset
                master_conversation.write({
                    'last_message_content': latest_message.content,
                    'last_message_time': latest_message.created_at,
                })
                _logger.info(">>> Master conversation fields updated. Latest message ID: %s (created_at: %s)", latest_message.id, latest_message.created_at)
            else:
                # Trường hợp không có tin nhắn nào sau khi gộp (rất hiếm, chỉ xảy ra nếu tất cả cuộc hội thoại ban đầu đều không có tin nhắn)
                 master_conversation.write({
                    'last_message_content': False,
                    'last_message_time': False,
                })
                 _logger.warning(">>> No messages found for master conversation %s after relinking. Clearing last message fields.", master_conversation.id)

            _logger.info(">>> Master conversation fields updated successfully.")
        except Exception as e:
            _logger.error(">>> Error updating master fields: %s", e, exc_info=True)
            raise UserError(_("Đã xảy ra lỗi khi cập nhật thông tin cuối cùng của cuộc hội thoại: %s") % e)


        # 3. Xóa các cuộc hội thoại phụ đã được gộp
        # Bước này phải làm SAU khi các tin nhắn đã được relink thành công
        _logger.info(">>> Unlinking secondary conversations: %s...", conversations_to_merge.ids)
        try:
            # Check if conversations_to_merge is not empty before unlink
            if conversations_to_merge:
                conversations_to_merge.unlink()
                _logger.info(">>> Secondary conversations unlinked successfully.")
            else:
                _logger.info(">>> No secondary conversations to unlink.")

        except Exception as e:
            _logger.error(">>> Error unlinking conversations: %s", e, exc_info=True)
            raise UserError(_("Đã xảy ra lỗi khi xóa các cuộc hội thoại cũ: %s") % e)


        _logger.info(">>> Merge action completed for master conversation %s.", master_conversation.id)

        # 4. Trả về action để làm mới view hoặc hiển thị thông báo
        # Option 1: Hiển thị thông báo thành công
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Thành công"),
                'message': _("%s cuộc hội thoại đã được gộp vào cuộc hội thoại #%s.") % (len(conversations_to_merge), master_conversation.id),
                'type': 'success',
                'sticky': False, # Thông báo sẽ tự biến mất
            }
        }

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

    def send_message_to_chatwoot(self):
        if self.message_content:
            content = self.message_content
            self.env['chatopia.message'].create({
                'conversation_id': self.id,
                'content': content,
                'sender': self.env.user.name,
            })

            # Lấy các giá trị từ conversation
            chatwoot_conversation_id = self.chatwoot_conversation_id

            # Tạo URL Chatwoot
            # chatwoot_url = f"https://app.chatwoot.com/api/v1/accounts/115807/conversations/{chatwoot_conversation_id}/messages"
            chatwoot_url = f"https://lvshipper.io.vn/api/v1/accounts/1/conversations/{chatwoot_conversation_id}/messages"
            # webhook_url = "https://webhook.site/8f91ab2c-5555-4a45-80ed-40beb5de5c8d"

            payload = {
                "content": content,
                "message_type": "outgoing"
            }

            _logger.info(f"Payload: {payload}")

            headers = {
                "Content-Type": "application/json",
                "api_access_token": "gg5vjCgX57BDKoCTzSZfkEe4"
            }

            urls = [chatwoot_url]

            def send_to_url(url, data, headers):
                try:
                    _logger.info(f"Sending message to URL: {url}")
                    response = requests.post(url, data=json.dumps(data), headers=headers if url == chatwoot_url else {"Content-Type": "application/json"})
                    response.raise_for_status()
                    _logger.info("Request successful")
                    _logger.info(f"Response Status Code: {response.status_code}")
                    _logger.info(f"Response Text: {response.text}")
                    return response.status_code == 200, response.text
                except requests.exceptions.RequestException as e:
                    _logger.error(f"Error sending request to {url}: {e}")
                    return False, str(e)

            results = []
            for url in urls:
                success, message = send_to_url(url, payload, headers if url == chatwoot_url else {"Content-Type": "application/json"})
                results.append((url, success, message))

            all_successful = all(success for url, success, message in results)

            if all_successful:
                self.message_content = False
                return True
            else:
                error_messages = "\n".join([f"URL: {url}, Success: {success}, Message: {message}" for url, success, message in results])
                raise Exception(f"Gửi tin nhắn thất bại! \n{error_messages}")

        else:
            _logger.warning("Không có nội dung tin nhắn để gửi.")
            return False

    def send_message(self):
        try:
            self.send_message_to_chatwoot()
        except Exception as e:
            _logger.exception("Lỗi khi gửi đến Chatwoot: %s", e)
            raise UserError(_("Gửi tin nhắn thất bại đến Chatwoot: %s") % e)