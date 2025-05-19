# from odoo import http
# import logging

# _logger = logging.getLogger(__name__)

# class ChatopiaWebhook(http.Controller):
#     @http.route('/webhook/chatwoot', type='http', auth='public', methods=['POST'], csrf=False, website=False)
#     def chatwoot_webhook(self, **kwargs):
#         _logger.info("Webhook endpoint hit")
#         return 'OK'

#     @http.route('/test', type='http', auth='public', methods=['GET'])
#     def test_endpoint(self, **kwargs):
#         _logger.info("Test endpoint hit")
#         return 'Test OK'