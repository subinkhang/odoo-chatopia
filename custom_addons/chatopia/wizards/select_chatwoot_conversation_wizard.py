# wizards/select_chatwoot_conversation_wizard.py
from odoo import api, fields, models, _
from odoo.exceptions import UserError
# Không cần import json nữa
import logging
_logger = logging.getLogger(__name__)

class SelectChatwootConversationWizard(models.TransientModel):
    _name = 'chatopia.select.chatwoot.conversation.wizard'
    _description = 'Wizard to Manually Input Target Chatwoot Conversation ID'

    conversation_odoo_id = fields.Many2one(
        'chatopia.conversation', 
        string='Odoo Conversation Ref', # Đổi tên label cho rõ
        required=True, 
        readonly=True,
    )
    message_content_display = fields.Text( # Để hiển thị nội dung
        string='Message Content', 
        required=True, 
        readonly=True, 
    )
    
    available_ids_info = fields.Text( # Để hiển thị các ID có sẵn
        string="Information",
        readonly=True,
    )

    target_chatwoot_conv_id_input = fields.Integer( # Trường để người dùng nhập ID
        string="Target Chatwoot Conversation ID",
        required=True,
        help="Enter the Chatwoot Conversation ID you want to send this message to."
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        context = self.env.context
        _logger.info("MANUAL WIZARD default_get: Context: %s, Fields: %s", context, fields_list)

        res['conversation_odoo_id'] = context.get('default_conversation_odoo_id')
        res['message_content_display'] = context.get('default_message_content_display')
        res['available_ids_info'] = context.get('default_available_ids_info')
        res['target_chatwoot_conv_id_input'] = context.get('default_target_chatwoot_conv_id_input')
        
        _logger.info("MANUAL WIZARD default_get: Returning res: %s", res)
        return res

    def action_confirm_send(self):
        self.ensure_one()
        if not self.target_chatwoot_conv_id_input or self.target_chatwoot_conv_id_input <= 0:
            raise UserError(_("Please enter a valid positive Chatwoot Conversation ID."))
        
        # target_chatwoot_conv_id_input đã là Integer
        target_id = self.target_chatwoot_conv_id_input 
        
        _logger.info("MANUAL WIZARD action_confirm_send: Sending to CW ID %s, Odoo Conv %s", 
                     target_id, self.conversation_odoo_id.id)
        
        success = self.conversation_odoo_id.process_send_to_selected_chatwoot_id(
            self.message_content_display, # Nội dung lấy từ trường hiển thị
            target_id
        )
        
        if success:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Message Sent'),
                'message': _("Message sent to Chatwoot Conversation ID %s.") % target_id,
                'type': 'success', 'sticky': False,
            }}
        else:
            # Lỗi đã được log, hiển thị thông báo chung
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Send Error'),
                'message': _("Failed to send message to Chatwoot Conversation ID %s. Check logs for details.") % target_id,
                'type': 'danger', 'sticky': True,
            }}
        # Wizard sẽ tự đóng nếu không có lỗi UserError và không có action cụ thể nào khác được trả về
        # Hoặc bạn có thể thêm return {'type': 'ir.actions.act_window_close'}