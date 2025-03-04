{
    'name': 'CreativeMinds',
    'version': '1.0',
    'icon': '/creativeminds/static/description/icon.png',
    'summary': 'Modulo para la gestion de proyectos',
    'description': """
        Gestion de proyectos
    """,
    'author': 'Heily Madelay Ajila Tandazo, Daniel Gonzalez Esteban',
    'category': 'Marketing',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'project',
        'mail',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'data/dashboard_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}