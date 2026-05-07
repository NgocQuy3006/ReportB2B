# -*- coding: utf-8 -*-
# Author: Lã Tuấn Kiệt
# Copyright © 2017 B2B Technology
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields
from odoo.tools import (
    DEFAULT_SERVER_DATETIME_FORMAT,
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT,
)
import time
import re
import logging
_logger = logging.getLogger(__name__)


class AbstractExcelReport(models.AbstractModel):
    _name = 'report.b2b_base_report.abstract_excel_report'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Abstract Excel used for export report data to Excel file.'

    # ==========================
    # 🔧 INIT (Fixed for Odoo 18)
    # ==========================
    def __init__(self, env, registry=None, name=None):
        """Updated init for Odoo 18 (expects env, registry, name)."""
        super().__init__(env, registry, name)
        cls = type(self)

        # Main worksheet and workbook references
        cls.workbook = None
        cls.sheet = None

        # Report runtime info
        cls.company_id = None
        cls.running_time = None
        cls.date_format = DEFAULT_SERVER_DATE_FORMAT
        cls.time_format = DEFAULT_SERVER_TIME_FORMAT
        cls.datetime_format = DEFAULT_SERVER_DATETIME_FORMAT

        # Columns and headers
        cls.header_row = None
        cls.columns = None
        cls.row_pos = 0

        # Header formats
        cls.format_header_com_name = None
        cls.format_header_com_info = None
        cls.format_header_runtime = None
        cls.format_header_title = None
        cls.format_header_param = None

        # Body header formats
        cls.format_body_header = None
        cls.format_body_header_left = None
        cls.format_body_header_right = None

        # Group formats
        cls.format_group_normal = None
        cls.format_group_amount = None
        cls.format_group_number = None
        cls.format_group_percent = None

        # Data formats
        cls.format_normal = None
        cls.format_string = None
        cls.format_date = None
        cls.format_datetime = None
        cls.format_amount = None
        cls.format_number = None
        cls.format_percent = None

        # Footer formats
        cls.format_footer_normal = None
        cls.format_footer_datetime = None
        cls.format_footer_bold = None
        cls.format_footer_amount = None
        cls.format_footer_number = None

    # ==========================
    # ⚙️ CORE GENERATE LOGIC
    # ==========================
    def get_workbook_options(self):
        """Override get_workbook_options to reduce memory."""
        return {'constant_memory': True}

    def generate_xlsx_report(self, workbook, data, objects):
        """Main entry point for XLSX export."""
        report = data or {}
        cls = type(self)

        cls.company_id = (
            report.get('data', {}).get('company_id')
            or self.env.user.company_id.id
        )

        if report.get('data', {}).get('form', {}).get('used_context'):
            ctx = report['data']['form']['used_context']
            cls.date_format = ctx.get('date_format', DEFAULT_SERVER_DATE_FORMAT)
            cls.time_format = ctx.get('time_format', DEFAULT_SERVER_TIME_FORMAT)
            cls.datetime_format = f"{cls.date_format} {cls.time_format}"

        cls.row_pos = 0
        cls.running_time = 'Run Report: ' + time.strftime(cls.datetime_format)

        # Determine sheet name and title
        report_name = self._get_report_name(report)
        report_title = self._get_report_title(report)
        if not report_name:
            report_name = (report_title or 'Report')[:31]

        # Prepare sheet
        cls.workbook = workbook
        cls.sheet = workbook.add_worksheet(report_name)
        cls.columns = self._get_report_columns(report)
        cls.header_row = self._get_header_row()
        filters = self._get_report_filters(report)
        report_footer = self._get_report_footer()

        # Generate formats
        self._define_formats(workbook)
        self._set_column_width()

        # Write header sections
        self._write_report_company(report)
        self._write_report_title(report_title)
        self._write_filters(filters)

        # Write main content
        self._generate_report_content(workbook, report)

        # Write footer
        self._write_report_footer(report_footer)

    # ==========================
    # 🧱 FORMATS
    # ==========================
    def _define_formats(self, workbook):
        cls = type(self)

        # Header formats
        cls.format_header_com_name = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10, 'bold': True})
        cls.format_header_com_info = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 9})
        cls.format_header_runtime = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10,
             'italic': True, 'font_color': 'red'})
        cls.format_header_title = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 14,
             'valign': 'vcenter', 'bold': True})
        cls.format_header_param = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10,
             'valign': 'vcenter', 'font_color': 'blue'})

        # Body header
        base_header = {
            'font_name': 'Times New Roman',
            'font_size': 10,
            'text_wrap': True,
            'bold': True,
            'valign': 'vcenter',
            'border': True,
            'bg_color': '#D7E4BC'
        }
        cls.format_body_header = workbook.add_format({**base_header, 'align': 'center'})
        cls.format_body_header_left = workbook.add_format({**base_header, 'align': 'left'})
        cls.format_body_header_right = workbook.add_format({**base_header, 'align': 'right'})

        # Currency formats
        currency = self.env['res.company'].browse(cls.company_id).currency_id
        fractor = '0' * currency.decimal_places
        if fractor:
            fractor = '.' + fractor
        fmt_name = f'_(* #,##0{fractor}_);[Red]_(* (#,##0{fractor});_(* "-"_);_(@_)'

        cls.format_group_normal = workbook.add_format({'font_name': 'Times New Roman', 'bold': True})
        cls.format_group_amount = workbook.add_format({'font_name': 'Times New Roman',
                                                       'bold': True, 'num_format': fmt_name})
        cls.format_group_number = workbook.add_format({'font_name': 'Times New Roman',
                                                       'bold': True, 'num_format': '#,##0.00'})
        cls.format_group_percent = workbook.add_format({'font_name': 'Times New Roman',
                                                        'bold': True, 'num_format': '#,##0.00%'})

        # Date/time
        fmt_date = self.date_format.replace('%d', 'dd').replace('%m', 'mm').replace('%y', 'yy').replace('%Y', 'yyyy')
        fmt_date = fmt_date.lower().replace('%b', 'mmm')
        fmt_time = self.time_format.replace('%H', 'HH').replace('%M', 'MM').replace('%S', 'SS').replace('%p', 'AM/PM')
        fmt_datetime = f"{fmt_date} {fmt_time}"

        # Body formats
        cls.format_normal = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 10, 'valign': 'vcenter'})
        cls.format_string = workbook.add_format({'font_name': 'Times New Roman', 'num_format': '@'})
        cls.format_amount = workbook.add_format({'font_name': 'Times New Roman', 'num_format': fmt_name})
        cls.format_number = workbook.add_format({'font_name': 'Times New Roman', 'num_format': '#,##0.00'})
        cls.format_percent = workbook.add_format({'font_name': 'Times New Roman', 'num_format': '#,##0.00%'})
        cls.format_date = workbook.add_format({'font_name': 'Times New Roman', 'num_format': fmt_date})
        cls.format_datetime = workbook.add_format({'font_name': 'Times New Roman', 'num_format': fmt_datetime})

        # Footer
        cls.format_footer_normal = workbook.add_format({'align': 'center'})
        cls.format_footer_datetime = workbook.add_format({'italic': True, 'align': 'center'})
        cls.format_footer_bold = workbook.add_format({'bold': True, 'align': 'center'})
        cls.format_footer_amount = workbook.add_format({'bold': True, 'num_format': fmt_name})
        cls.format_footer_number = workbook.add_format({'bold': True, 'num_format': '#,##0.00'})

    # ==========================
    # 🧩 UTILS + WRITING
    # ==========================
    def _set_column_width(self):
        for pos, col in self.columns.items():
            self.sheet.set_column(pos, pos, col.get('width', 10))
    
    def _merge_safe(self, row1, col1, row2, col2, value, fmt):
        """Ghi log chi tiết từng vùng merge, tránh lỗi merge trùng."""
        key = (row1, col1, row2, col2)
        try:
            _logger.warning("🧩 [Merge] Trying: %s | value=%s", key, value)
            self.sheet.merge_range(row1, col1, row2, col2, value or '', fmt)
            _logger.warning("✅ [Merge OK] %s", key)
        except Exception as e:
            _logger.error("💥 [Merge ERROR] %s → %s", key, e)
            try:
                self.sheet.write(row1, col1, value or '', fmt)
                _logger.warning("✏️ [Fallback Write] %s", key)
            except Exception as ee:
                _logger.error("⚠️ Write fallback failed at %s: %s", key, ee)


    def _write_report_company(self, report):
        col_pos = self._get_col_report_time()
        self.sheet.write(self.row_pos, col_pos, self.running_time, self.format_header_runtime)

        if self.company_id:
            company = self.env['res.company'].browse(self.company_id)
            address = f"{company.street or ''} - {company.state_id.name if company.state_id else company.city or ''}"
            tax = f"MST: {company.vat or 'XXXXXXXXXX'}"
            self.sheet.write(self.row_pos, 0, company.name, self.format_header_com_name)
            self.sheet.write(self.row_pos + 1, 0, address, self.format_header_com_info)
            self.sheet.write(self.row_pos + 2, 0, tax, self.format_header_com_info)
        type(self).row_pos += 3
        self.sheet.write(self.row_pos, 0, " ")
        type(self).row_pos += 1

    def _write_report_title(self, title):
        self.sheet.set_row(self.row_pos, 20)
        merge = self._title_merge_range()
        if merge:
            self.sheet.merge_range(self.row_pos, 0, self.row_pos, len(self.columns) - 1,
                                   title, self.format_header_title)
        else:
            self.sheet.write(self.row_pos, 0, title, self.format_header_title)
        type(self).row_pos += 1

    def _write_filters(self, filters):
        col_name = 0
        name_cols = self._get_col_count_filter_name()
        val_cols = self._get_col_count_filter_value()
        merge = self._filter_merge_range()

        for title, value in filters:
            if merge:
                self.sheet.merge_range(self.row_pos, col_name, self.row_pos, col_name + name_cols - 1,
                                       title, self.format_header_param)
                self.sheet.merge_range(self.row_pos, name_cols, self.row_pos, name_cols + val_cols - 1,
                                       value, self.format_header_param)
            else:
                self.sheet.write(self.row_pos, col_name, title, self.format_header_param)
                self.sheet.write(self.row_pos, col_name + name_cols, value, self.format_header_param)
            type(self).row_pos += 1
        self.sheet.write(self.row_pos, 0, " ")
        type(self).row_pos += 1

    # ==========================
    # 📄 ABSTRACT METHODS (safe defaults)
    # ==========================
    def _generate_report_content(self, workbook, report):
        raise NotImplementedError()

    def _write_report_footer(self, footer):
        pass

    def _get_report_name(self, report):
        return False

    def _get_report_title(self, report):
        raise NotImplementedError()

    def _get_report_columns(self, report):
        raise NotImplementedError()

    def _get_report_filters(self, report):
        raise NotImplementedError()

    def _get_header_row(self):
        """Default header rows = 1 (safe fallback)."""
        return 1

    def _get_col_report_time(self):
        """Default column index for runtime info."""
        return 0

    def _get_col_count_filter_name(self):
        """Default number of columns for filter name."""
        return 1

    def _get_col_count_filter_value(self):
        """Default number of columns for filter value."""
        return 1

    def _get_col_pos_initial_balance_label(self):
        raise NotImplementedError()

    def _get_col_pos_final_balance_label(self):
        raise NotImplementedError()

    def _get_report_footer(self):
        return False

    def _title_merge_range(self):
        return True

    def _filter_merge_range(self):
        return False

    def write_group_header(self, line_object):
        """Default group header (safe for all reports)."""
        value = line_object.get('name', '')
        self.sheet.set_row(self.row_pos, 20)
        self.sheet.merge_range(self.row_pos, 0, self.row_pos, len(self.columns) - 1,
                               value, self.format_group_normal)
        type(self).row_pos += 1

    def write_body_header(self):
        """Default method to render column headers (can be overridden)."""
        if not self.columns:
            return
        self.sheet.set_row(self.row_pos, 25)
        for col_pos, column in self.columns.items():
            header_text = column.get('header', '')
            align = column.get('align', 'center')
            fmt = self.format_body_header
            if align == 'left':
                fmt = self.format_body_header_left
            elif align == 'right':
                fmt = self.format_body_header_right
            self.sheet.write(self.row_pos, col_pos, header_text, fmt)
        type(self).row_pos += 1

    def write_line_blank(self, cell_format=None):
        """Insert a blank line with optional format (default: normal border top)."""
        fmt = cell_format or self.format_footer_normal
        col_count = len(self.columns)
        if col_count == 0:
            return
        for col_pos in range(col_count):
            self.sheet.write(self.row_pos, col_pos, "", fmt)
        type(self).row_pos += 1

    def write_line(self, line):
        """Write a single data line to the worksheet based on column definitions."""
        if not self.columns:
            return

        for col_pos, column in self.columns.items():
            field = column.get('field')
            field2 = column.get('field2')  # dùng cho OU hoặc Total
            cell_type = column.get('type', 'string')
            fmt = self.format_string

            # Chọn định dạng theo kiểu dữ liệu
            if cell_type == 'number':
                fmt = self.format_number
            elif cell_type == 'amount':
                fmt = self.format_amount
            elif cell_type == 'percent':
                fmt = self.format_percent
            elif cell_type == 'date':
                fmt = self.format_date
            elif cell_type == 'datetime':
                fmt = self.format_datetime

            # Lấy giá trị từ dòng dữ liệu
            value = line.get(field, '')

            # 🧩 Nếu value là dict (OU hoặc tổng hợp) → lấy subfield
            if isinstance(value, dict):
                if field2 and field2 in value:
                    value = value[field2]
                else:
                    value = value.get('total') or next(iter(value.values()), 0)

            # Nếu vẫn là dict (trường hợp dữ liệu lỗi) → bỏ qua
            if isinstance(value, dict):
                value = ''

            self.sheet.write(self.row_pos, col_pos, value, fmt)

        type(self).row_pos += 1

