{
    'name': 'Chatopia',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Omnichannel, centralized chat system',
    'description': """
        Chatopia is an omnichannel, centralized chat system.
    """,
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        # 'data/chatopia_mock_data.xml',
        'views/chatopia_menu.xml',
        'views/chatopia_views.xml'
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}