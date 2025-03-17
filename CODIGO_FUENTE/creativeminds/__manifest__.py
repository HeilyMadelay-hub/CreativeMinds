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
        'security/ir.model.access.csv',  # SIEMPRE primero la seguridad
        'views/views.xml',               # Principal vista consolidada
        'views/templates.xml',           # Vistas para renderizado web
        'reports/reports.xml',           # Informes PDF o QWeb
    ],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,

}