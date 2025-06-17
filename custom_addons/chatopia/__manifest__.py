{
    'name': 'Chatopia',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Omnichannel, centralized chat system',
    'description': """
        Chatopia is an omnichannel, centralized chat system.
    """,
    'depends': ['base', 'sale', 'crm', 'mail'],
    'assets': {
        'web.assets_backend': [
            '/chatopia/static/src/css/style.css',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/chatopia_mock_data.xml',
        'views/chatopia_views.xml',         # <--- PHẢI ĐƯỢC LOAD TRƯỚC
        'views/my_custom_report.xml',
        'views/super_chatopia_view.xml',         # <--- PHẢI ĐƯỢC LOAD TRƯỚC
        'views/chatopia_menu.xml',         # <--- LOAD SAU
        'views/res_partner_views.xml',
        'views/chatopia_actions.xml',
        'wizards/select_chatwoot_conversation_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}