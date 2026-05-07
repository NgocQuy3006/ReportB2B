# -*- coding: utf-8 -*-
# Author: Lã Tuấn Kiệt
# Copyright © 2017 B2B Technology
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'B2B Base Report',
    'version': '19.0.0.0.1',
    'category': 'Bispro/Tools',
    'summary': 'B2B Base Report Framework with Excel Export',
    'description': """
Centralized base report system for all B2B projects.
Includes OWL3 web reports and XLSX export capability.
""",
    'author': 'B2B Technology, Kiet La',
    'website': 'https://b2btech.com.vn',
    'depends': ['report_xlsx', 'b2b_base', 'b2b_operating_unit'],
    'data': [
        'views/report_paper.xml',
        'views/report_menu.xml',           # Action & Menus
    ],
    'assets': {
        'web.assets_backend': [
            "b2b_base_report/static/src/css/select2.min.css",
            # "b2b_base_report/static/src/css/report_theme.css",
            # "b2b_base_report/static/src/css/b2b_base_report.css",
            "b2b_base_report/static/src/js/select2_loader.js",
            "b2b_base_report/static/src/js/product_registers_report.js",
            "b2b_base_report/static/src/js/partner_registers_report.js",
            "b2b_base_report/static/src/xml/report_product_registers.xml",
            "b2b_base_report/static/src/xml/report_partner_registers.xml",
        ],
    },
    'installable': True,
    'application': True,
    'license': 'AGPL-3',
}
