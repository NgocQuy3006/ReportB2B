# -*- coding: utf-8 -*-
# Author: Lã Tuấn Kiệt
# Copyright © 2017 B2B Technology
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, _


class PartnerRegistersXlsx(models.AbstractModel):
    _name = 'report.b2b_base_report.partner_registers_xlsx'
    _inherit = 'report.b2b_base_report.abstract_excel_report'
    _description = "Partner Registers XLSX Report - List of partners in system."

    # ==================================
    # 🧱 DEFINE CUSTOM FORMATS
    # ==================================
    def _define_formats(self, workbook):
        """Extend base formats for sub-line (contacts) and STT column."""
        super()._define_formats(workbook)
        cls = type(self)

        # Sub-line (contact row)
        cls.format_sub_string = workbook.add_format({
            'font_name': 'Times New Roman',
            'font_size': 9,
            'italic': True,
            'valign': 'vcenter',
            'left': 1,
            'right': 1,
            'bottom': 3,
            'num_format': '@',
        })

        # STT format (centered index)
        cls.format_index = workbook.add_format({
            'font_name': 'Times New Roman',
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
        })

    # ==================================
    # 🏷️ BASIC REPORT INFO
    # ==================================
    def _get_report_name(self, report):
        """Worksheet name (max 31 chars)."""
        return 'partners'

    def _get_report_title(self, report):
        """Title displayed on top of report."""
        return _('PARTNER REGISTERS')

    # ==================================
    # 🧾 COLUMN STRUCTURE
    # ==================================
    def _get_report_columns(self, report):
        """Define all report columns (consistent with HTML layout)."""
        return {
            0: {'header': _('No'), 'field': 'index', 'width': 6, 'align': 'center'},
            1: {'header': _('Code'), 'field': 'code', 'width': 12},
            2: {'header': _('Short Name'), 'field': 'short_name', 'width': 20},
            3: {'header': _('Full Name'), 'field': 'full_name', 'width': 35},
            4: {'header': _('Address'), 'field': 'address', 'width': 35},
            5: {'header': _('City'), 'field': 'city', 'width': 15},
            6: {'header': _('Province'), 'field': 'province', 'width': 15},
            7: {'header': _('Country'), 'field': 'country', 'width': 15},
            8: {'header': _('Tax Registry'), 'field': 'vat', 'width': 18},
            9: {'header': _('Category'), 'field': 'category', 'width': 25},
            10: {'header': _('Phone'), 'field': 'phone', 'width': 15},
            # 11: {'header': _('Mobile'), 'field': 'mobile', 'width': 15},
            11: {'header': _('Activation'), 'field': 'activate_flag', 'width': 12},
        }

    # ==================================
    # 🔍 FILTER DISPLAY
    # ==================================
    def _get_report_filters(self, report):
        """Render filters section above the table."""
        form = report.get('data', {}).get('form', {}) or {}

        # Activation filter
        activate_flag = form.get('activate_flag', 'All')

        # Partner type filter
        partner_type = form.get('partner_type', 'all')
        if partner_type == 'customer':
            partner_type_name = _('Customer Only')
        elif partner_type == 'supplier':
            partner_type_name = _('Supplier Only')
        else:
            partner_type_name = _('All Partners')

        # Tags filter
        tags = form.get('partner_tags') or form.get('tags') or []
        if tags:
            tag_names = ', '.join(
                [t.get('text', '') if isinstance(t, dict) else str(t) for t in tags]
            )
        else:
            tag_names = _('All')

        return [
            [_('Activation'), activate_flag],
            [_('Partner Type'), partner_type_name],
            [_('Tags'), tag_names],
        ]

    # ==================================
    # ⚙️ LAYOUT DEFINITIONS
    # ==================================
    def _get_header_row(self):
        return 1

    def _get_col_report_time(self):
        return 5

    def _get_col_count_filter_name(self):
        return 1

    def _get_col_count_filter_value(self):
        return 1

    # ==================================
    # 🧩 LINE WRITERS
    # ==================================
    def write_line(self, line):
        """Write one partner line (company)."""
        for col_pos, column in self.columns.items():
            field = column['field']
            value = line.get(field, "")

            # Cột STT
            if field == 'index':
                self.sheet.write(self.row_pos, col_pos, value, self.format_index)
                continue

            fmt = self.format_string
            self.sheet.write(self.row_pos, col_pos, value, fmt)

        type(self).row_pos += 1

    def write_body_header(self):
        """Header for the table."""
        self.sheet.set_row(self.row_pos, 35)
        super().write_body_header()

    def write_children(self, child):
        """Write contact (child partner) rows."""
        for col_pos, column in self.columns.items():
            field = column['field']
            value = child.get(field, "")

            # Dòng con không đánh số
            if field == 'index':
                self.sheet.write(self.row_pos, col_pos, "", self.format_sub_string)
                continue

            self.sheet.write(self.row_pos, col_pos, value, self.format_sub_string)
        type(self).row_pos += 1

    # ==================================
    # 🧩 CONTENT GENERATOR
    # ==================================
    def _generate_report_content(self, workbook, report):
        """Render partner list content (company + contacts)."""
        # Header dòng dữ liệu
        self.write_body_header()

        # Format separator
        end_format = workbook.add_format({'top': 1})

        for idx, line in enumerate(report.get('lines', []), start=1):
            line['index'] = idx
            self.write_line(line)

            # Write contact children
            for child in line.get('children', []):
                child['index'] = ""
                self.write_children(child)

        # Dòng trống cuối
        self.write_line_blank(end_format)
