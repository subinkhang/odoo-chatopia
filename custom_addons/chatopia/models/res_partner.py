from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def check_contact_exists(self, email_or_id):
        _logger.info(f"Received input: {email_or_id}")
        if not email_or_id:
            _logger.warning("Input is empty or None")
            return {'exists': False, 'chatwoot_conversation_id': False, 'x_chatwoot_contact_id': False}

        # Nếu đầu vào là số, thêm '@gmail.com' để khớp với định dạng email trong DB
        if isinstance(email_or_id, str) and email_or_id.isdigit():
            email = f"{email_or_id}@gmail.com"
        else:
            email = email_or_id  # Nếu đã là email thì giữ nguyên

        _logger.info(f"Converted email: {email}")

        # Tìm contact dựa trên email
        contact = self.search([('email', '=', email)], limit=1)
        _logger.info(f"Found contact: {contact}")

        if not contact:
            _logger.info("Contact not found")
            return {'exists': False, 'chatwoot_conversation_id': False, 'x_chatwoot_contact_id': False}

        # Contact tồn tại, đặt exists = True
        exists = True
        _logger.info("Contact exists")

        # Lấy name của contact
        contact_name = contact.name
        _logger.info(f"Contact name: {contact_name}")

        # Tìm conversation có sender_name khớp với name của contact
        conversation = self.env['chatopia.conversation'].search(
            [('sender_name', '=', contact_name)], limit=1
        )
        _logger.info(f"Found conversation: {conversation}")

        if not conversation:
            _logger.info("Conversation not found for this contact")
            return {'exists': True, 'chatwoot_conversation_id': False, 'x_chatwoot_contact_id': False}

        # Trả về exists, chatwoot_conversation_id và x_chatwoot_contact_id
        return {
            'exists': True,
            'chatwoot_conversation_id': conversation.chatwoot_conversation_id,
            'x_chatwoot_contact_id': conversation.x_chatwoot_contact_id
        }