# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Handle easily multiple variants and sets on Sales Orders like Website e-shop',
    'summary': 'Handle the addition/removal of multiple variants from '
               'product template an sets into the sales order like Website e-shop',
    'version': '11.0.1.0.0',
    'author': 'Rosen Vladimirov,'
              'dXFactory Ltd.',
    'category': 'Sale',
    'license': 'AGPL-3',
    'website': 'https://www.dxfactory.eu',
    'depends': [
        'sale',
    ],
    'demo': [],
    'data': [
        'wizard/sale_manage_variant_view.xml',
        'views/sale_order_view.xml',
    ],
    'installable': True,
}
