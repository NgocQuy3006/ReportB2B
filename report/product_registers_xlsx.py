# -*- coding: utf-8 -*-
# Author: Lã Tuấn Kiệt
# Copyright © 2017 B2B Technology
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, _


class ProductRegistersXlsx(models.AbstractModel):
    _name = 'report.b2b_base_report.product_registers_xlsx'
    _inherit = 'report.b2b_base_report.abstract_excel_report'
    _description = "Product Registers XLSX Report - List of products in system."

    # ==================================
    # 🧱 DEFINE CUSTOM FORMATS
    # ==================================
    def _define_formats(self, workbook):
        """Extend base formats with sub-row formats and STT column."""
        super()._define_formats(workbook)
        cls = type(self)
        fmt_name = '_(* #,##0{0}_);[Red]_(* (#,##0{0});_(* "-"_);_(@_)'

        # Sub-line (variant)
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
        cls.format_sub_number = workbook.add_format({
            'font_name': 'Times New Roman',
            'font_size': 9,
            'italic': True,
            'valign': 'vcenter',
            'left': 1,
            'right': 1,
            'bottom': 3,
            'num_format': fmt_name.format('.00'),
        })

        # STT format
        cls.format_index = workbook.add_format({
            'font_name': 'Times New Roman',
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
        })

    # ==================================
    # 🏷️ BASIC REPORT INFO
    # ==================================
    def _get_report_name(self, report):
        """Worksheet name (max 31 chars)."""
        return 'products'

    def _get_report_title(self, report):
        """Title displayed on top of report."""
        return _('PRODUCT REGISTERS')

    # ==================================
    # 🧾 COLUMN STRUCTURE
    # ==================================
    def _get_report_columns(self, report):
        """Define all report columns."""
        return {
            0: {'header': _('No'), 'field': 'index', 'width': 6, 'align': 'center'},  # ✅ STT column
            1: {'header': _('Def Code'), 'field': 'code', 'width': 12},
            2: {'header': _('Short Cut'), 'field': 'short_name', 'width': 25},
            3: {'header': _('Product Name'), 'field': 'name', 'width': 45},
            4: {'header': _('UoM'), 'field': 'unit_uom', 'width': 10},
            5: {'header': _('Category'), 'field': 'categ_name', 'width': 25},
            6: {'header': _('Product Type'), 'field': 'product_type', 'width': 20},
            7: {'header': _('Unit Cost'), 'field': 'cost', 'type': 'number', 'width': 14},
            8: {'header': _('Sale Price'), 'field': 'sale_price', 'type': 'number', 'width': 14},
            9: {'header': _('Weight'), 'field': 'weight', 'type': 'number', 'width': 11},
            10: {'header': _('Volume'), 'field': 'volume', 'type': 'number', 'width': 11},
            11: {'header': _('Activation'), 'field': 'flag', 'width': 11},
        }

    # ==================================
    # 🔍 FILTER DISPLAY
    # ==================================
    def _get_report_filters(self, report):
        """Render filters section above the table."""
        filters = report.get('data', {}).get('form', {})

        # Category filter
        if filters.get('categories'):
            category = ', '.join([c.get('text', '') for c in filters['categories']])
        else:
            category = _('All')

        # Product Type filter
        _type = filters.get('product_type', 'all')
        product_type = _('All Product')
        if _type == 'product':
            product_type = _('Storable Product')
        elif _type == 'consu':
            product_type = _('Consumable')
        elif _type == 'service':
            product_type = _('Service')

        return [
            [_('Category'), category],
            [_('Product Type'), product_type],
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
        """Write one product line (with STT support)."""
        for col_pos, column in self.columns.items():
            field = column['field']
            value = line.get(field, "")
            cell_type = column.get('type', 'string')

            # Cột STT (index)
            if field == 'index':
                self.sheet.write(self.row_pos, col_pos, value, self.format_index)
                continue

            # Các cột còn lại
            if cell_type == 'number':
                fmt = self.format_number
            else:
                fmt = self.format_string

            self.sheet.write(self.row_pos, col_pos, value, fmt)

        type(self).row_pos += 1

    def write_body_header(self):
        self.sheet.set_row(self.row_pos, 35)
        super().write_body_header()

    def write_children(self, child):
        """Write attribute/variant rows."""
        for col_pos, column in self.columns.items():
            cell_type = column.get('type', 'string')
            cell_format = self.format_sub_string
            value = child.get(column['field'], '')

            if column['field'] == 'index':
                # Dòng con không đánh số
                self.sheet.write(self.row_pos, col_pos, "", self.format_sub_string)
                continue

            if cell_type == 'number':
                cell_format = self.format_sub_number

            self.sheet.write(self.row_pos, col_pos, value, cell_format)
        type(self).row_pos += 1

    # ==================================
    # 🧩 CONTENT GENERATOR
    # ==================================
    def _generate_report_content(self, workbook, report):
        """Render product list content with attribute lines if enabled."""
        data = report.get('data', {}).get('form', {})
        show_attribute = data.get('is_show_attribute', False)

        # Header dòng dữ liệu
        self.write_body_header()

        # Format phân cách cuối bảng
        end_format = workbook.add_format({'top': 1})

        for idx, line in enumerate(report.get('lines', []), start=1):
            line['index'] = idx  # ✅ đánh số thứ tự
            self.write_line(line)

            if show_attribute:
                children = line.get('children') or []
                for child in children:
                    child['index'] = ""  # dòng con không đánh số
                    self.write_children(child)

        # Dòng trống cuối
        self.write_line_blank(end_format)
