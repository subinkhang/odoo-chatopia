from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
import re

_logger = logging.getLogger(__name__)

class ChatConversation(models.Model):
    _name = 'chatopia.conversation'
    _description = 'Chat Conversation'

    name = fields.Char(string="Conversation Name")
    chatwoot_conversation_id = fields.Integer(string="Chatwoot Conversation ID")
    inbox_name = fields.Char(string="Inbox Name")
    sender_name = fields.Char(string="Sender Name")
    message_ids = fields.One2many('chatopia.message', 'conversation_id', string="Messages")
    contact_id = fields.Many2one('res.partner', string="Contact", required=True)
    message_content = fields.Text(string="Message Content")
    x_chatwoot_contact_id = fields.Char(string="Chatwoot Contact ID")
    x_chatwoot_inbox_id = fields.Integer(string="Chatwoot Inbox ID")
    last_message_content = fields.Text(string="Last Message Content")
    last_message_time = fields.Datetime(string="Last Message Time")
    avatar = fields.Binary(string="Avatar")

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

    def send_message_to_zalo(self):
        self.ensure_one()

        if not self.message_content:
            raise UserError(_("Vui lòng nhập nội dung tin nhắn trước khi gửi."))

        recipient_zalo_id, error_message = self._extract_zalo_user_id_from_email()

        if not recipient_zalo_id:
            raise UserError(error_message)

        content_to_send = self.message_content

        zalo_api_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
        zalo_access_token = "rz7BCcPlwqlJrSCwP6ZbITJLpJvv1BSEm_N342Ski3hXtf8v30R7E-N2XJCv0-yJZEJC1dW2j3MUyEekAa6N7D6dipOvUk0uyhQX0ILurtdAcwHx7s3dQSc4lrivMkGfqRsP1mrqoZpjoPy5NWV0CUxWenbLHSGNffgr2MjOoWcgiOr-6stP3wYqXW061D9rj-UjUtK5a42K_x5RHoUHOht2y6b92B9PWzJ9KdaJh7wSxlHPHW-sQhpWyMrlBTTjtjtp7nOHbIVWpyDHEGY_H-3KvarIBeP3a8lcOo1Elqxxy9r1JZ_iSlxwltG_5lTdxz-Z50PlqIF1rF8w1Mc4AS2nvY0aSfiBbgtk6LONdG2QgxiCStJZFAgoWJ9HVjKvexUC7aTqrZQGdueMS7drFPs_WKv6VU5kWuWGGM1tuqS"

        if not zalo_access_token:
            _logger.error("Thiếu Zalo Access Token trong cấu hình hệ thống.")
            raise UserError(_("Chưa cấu hình Zalo Access Token trong Hệ thống > Thông số kỹ thuật > Tham số hệ thống (vd: zalo.oa.access_token)."))

        payload = {
            "recipient": {
                "user_id": recipient_zalo_id
            },
            "message": {
                "text": content_to_send
            }
        }

        headers = {
            "Content-Type": "application/json",
            "access_token": zalo_access_token
        }

        _logger.info(f"Chuẩn bị gửi tin nhắn Zalo đến User ID: {recipient_zalo_id} (trích xuất từ contact {self.contact_id.id})")
        _logger.debug(f"Zalo Payload: {json.dumps(payload)}")

        try:
            _logger.info(f"Đang gửi request đến Zalo API: {zalo_api_url}")
            response = requests.post(zalo_api_url, data=json.dumps(payload), headers=headers, timeout=15)
            response.raise_for_status()

            response_data = response.json()
            _logger.info("Gửi request Zalo thành công.")
            _logger.info(f"Zalo Response Status Code: {response.status_code}")
            _logger.info(f"Zalo Response Body: {response_data}")

            zalo_error_code = response_data.get('error')
            zalo_error_message = response_data.get('message', '')
            if zalo_error_code is not None and zalo_error_code != 0:
                _logger.error(f"Zalo API trả về lỗi: Code={zalo_error_code}, Message='{zalo_error_message}' cho User ID: {recipient_zalo_id}")
                error_detail = f" (User ID: {recipient_zalo_id}, Lỗi Zalo: {zalo_error_message})"
                raise UserError(_("Zalo API báo lỗi khi gửi tin nhắn: %s%s") % (zalo_error_message, error_detail))

            self.env['chatopia.message'].create({
                'conversation_id': self.id,
                'content': content_to_send,
                'sender': self.env.user.name or 'Odoo User',
                'message_type': 'admin',
                'created_at': fields.Datetime.now(),
            })

            self.message_content = False
            _logger.info(f"Đã gửi tin nhắn thành công đến Zalo User ID: {recipient_zalo_id}")

            return True

        except requests.exceptions.Timeout as e:
            _logger.error(f"Lỗi gửi tin nhắn Zalo (Timeout) đến User ID {recipient_zalo_id}: {e}")
            raise UserError(_("Gửi tin nhắn tới Zalo thất bại do hết thời gian chờ. Vui lòng thử lại."))
        except requests.exceptions.HTTPError as e:
            error_details = e.response.text
            status_code = e.response.status_code
            try:
                error_json = e.response.json()
                error_details = f"Code: {error_json.get('error', 'N/A')}, Message: {error_json.get('message', e.response.text)}"
            except json.JSONDecodeError:
                pass
            _logger.error(f"Lỗi gửi tin nhắn Zalo (HTTP Error {status_code}) đến User ID {recipient_zalo_id}: {error_details}")
            raise UserError(_("Gửi tin nhắn tới Zalo thất bại. Lỗi HTTP %s: %s (Kiểm tra Access Token hoặc User ID có thể không hợp lệ/không tồn tại)") % (status_code, error_details))
        except requests.exceptions.RequestException as e:
            _logger.error(f"Lỗi kết nối khi gửi tin nhắn Zalo đến User ID {recipient_zalo_id}: {e}")
            raise UserError(_("Gửi tin nhắn tới Zalo thất bại. Không thể kết nối tới Zalo API: %s") % e)
        except Exception as e:
            _logger.exception(f"Lỗi không xác định khi gửi tin nhắn Zalo đến User ID {recipient_zalo_id}:")
            raise UserError(_("Đã xảy ra lỗi không mong muốn khi gửi tin nhắn Zalo: %s") % e)

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
            chatwoot_url = f"https://app.chatwoot.com/api/v1/accounts/115807/conversations/{chatwoot_conversation_id}/messages"
            webhook_url = "https://webhook.site/8f91ab2c-5555-4a45-80ed-40beb5de5c8d"

            payload = {
                "content": content,
                "message_type": "outgoing",
                "is_from_odoo": True
            }

            _logger.info(f"Payload: {payload}")

            headers = {
                "Content-Type": "application/json",
                "api_access_token": "S6f1JAc6oDpRcRM34tD1P4H8"
            }

            urls = [chatwoot_url, webhook_url]

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
                raise Exception(f"Gửi tin nhắn thất bại đến một số URL! \n{error_messages}")

        else:
            _logger.warning("Không có nội dung tin nhắn để gửi.")
            return False

    def send_message(self):
        if self.contact_id and self.contact_id.email:
            try:
                self.send_message_to_zalo()
            except Exception as e:
                _logger.exception("Lỗi khi gửi đến Zalo, chuyển sang Chatwoot: %s", e)
                try:
                    self.send_message_to_chatwoot()
                except Exception as e:
                    _logger.exception("Lỗi khi gửi đến Chatwoot: %s", e)
                    raise UserError(_("Gửi tin nhắn thất bại cả Zalo và Chatwoot: %s") % e)
        else:
            try:
                self.send_message_to_chatwoot()
            except Exception as e:
                _logger.exception("Lỗi khi gửi đến Chatwoot: %s", e)
                raise UserError(_("Gửi tin nhắn thất bại đến Chatwoot: %s") % e)