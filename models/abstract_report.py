# -*- coding: utf-8 -*-
# Author: Lã Tuấn Kiệt
# Copyright © 2017 B2B Technology
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, fields, _
from odoo.exceptions import UserError
from datetime import datetime, date
from odoo.tools import date_utils as du
import json


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            encoded_object = obj.isoformat()
        else:
            encoded_object =json.JSONEncoder.default(self, obj)
        return encoded_object


class AbstractReport(models.AbstractModel):
    _name = 'report.abstract_report'
    _description = 'Abstract Report used for design web report data.'

    # ---------------------------------------------
    # PRIVATE FUNCTIONS
    # ---------------------------------------------
    def _parse_report_date(self, value):
        if not value:
            return None
        for date_format in ("%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue
        raise UserError(_("Invalid date format: %s") % value)

    def _get_company(self, data):
        company = False
        company_value = data['form'].get('company')
        company_id = False
        if isinstance(company_value, list):
            company_id = company_value and company_value[0].get('id')
        elif isinstance(company_value, dict):
            company_id = company_value.get('id')
        elif company_value:
            company_id = company_value
        if company_id:
            company = self.env['res.company'].browse(int(company_id))
        return company

    def _get_dates_param(self, data):
        date_from, date_to = None, None
        if data['form'].get('date_from'):
            date_from = self._parse_report_date(data['form'].get('date_from')).strftime('%Y-%m-%d')
        if data['form'].get('date_to'):
            date_to = self._parse_report_date(data['form'].get('date_to')).strftime('%Y-%m-%d')
        return date_from, date_to

    def _get_date_param(self, data):
        date_get = None
        if data['form'].get('date_get'):
            date_get = self._parse_report_date(data['form'].get('date_get')).strftime('%Y-%m-%d')
        return date_get

    def _get_compare_dates_param(self, data):
        date_from_cmp, date_to_cmp = None, None
        if data['form'].get('date_from_cmp'):
            date_from_cmp = self._parse_report_date(data['form'].get('date_from_cmp')).strftime('%Y-%m-%d')
        if data['form'].get('date_to_cmp'):
            date_to_cmp = self._parse_report_date(data['form'].get('date_to_cmp')).strftime('%Y-%m-%d')
        return date_from_cmp, date_to_cmp

    def _get_warehouses_param(self, data):
        warehouse_ids = []
        if data['form'].get('warehouses', False):
            warehouse_ids.append(0)
            for i in data['form'].get('warehouses'):
                warehouse_ids.append(int(i['id']))
        return warehouse_ids

    def _get_categories_param(self, data):
        categ_ids = []
        if data['form'].get('categories', False):
            categ_ids.append(0)
            for i in data['form'].get('categories'):
                category = self.env['product.category'].browse(int(i.get('id')))
                categ_ids.append(category.id)
                if category.child_id:
                    categ_ids += self.env['product.category'].search([('id', 'child_of', category.child_id.ids)]).ids
        return categ_ids

    def _get_products_param(self, data):
        product_ids = []
        if data['form'].get('products', False):
            product_ids.append(0)
            for i in data['form'].get('products'):
                product_ids.append(int(i['id']))
        return product_ids

    def _get_partner_tags_param(self, data):
        partner_tags = []
        if data['form'].get('partner_tags', False):
            partner_tags.append(0)
            for i in data['form'].get('partner_tags'):
                tags = self.env['res.partner.category'].browse(int(i.get('id')))
                partner_tags.append(tags.id)
                if tags.child_ids:
                    partner_tags += self.env['res.partner.category'].search([('id', 'child_of', tags.child_ids.ids)]).ids
        return partner_tags

    def _get_partners_param(self, data):
        partner_ids = []
        if data['form'].get('partners', False):
            partner_ids.append(0)
            for i in data['form'].get('partners'):
                partner_ids.append(int(i['id']))
        return partner_ids

    def _get_operating_units_param(self, data):
        operating_units = []
        if data['form'].get('operating_units', False):
            operating_units.append(0)
            for i in data['form'].get('operating_units'):
                operating_units.append(int(i['id']))
        return operating_units

    def _get_group_accounts_param(self, data):
        """You will overrided and implemented this method"""
        pass

    def _get_accounts_param(self, data):
        account_ids = []
        if data['form'].get('accounts', False):
            account_ids.append(0)
            for i in data['form'].get('accounts'):
                account_ids.append(int(i['id']))
        return account_ids

    def _get_user_warehouse_clause(self, alias='sm'):
        user_locations = getattr(self.env.user, 'stock_location_ids', False)
        if not user_locations:
            return ""
        warehouse_ids = [0]
        warehouse_ids += self.env['stock.warehouse'].search([
            ('view_location_id', 'in', user_locations.ids)
        ]).ids
        return "\n                and {alias}.warehouse_id in {warehouse_ids}".format(
            alias=alias,
            warehouse_ids=tuple(warehouse_ids),
        )

    def convert_date_for_sql(self, origin_date, get_end_date=False):
        origin_date = fields.Datetime.from_string(origin_date)
        if not get_end_date:
            date_get = du.start_of(origin_date, 'month')
        else:
            date_get = du.end_of(origin_date, 'month')

        return "'{}'::timestamp with time zone".format(date_get.strftime('%Y-%m-%d %H:%M:%S'))

    # ---------------------------------------------
    # BUSINESS METHODS
    # ---------------------------------------------
    def build_query(self, data):
        """
        :return: query string and it's params (if it need to set parameters when exec SQL)
        """
        raise NotImplementedError()

    @api.model
    def get_report_values(self, docids, data=None):
        if not data.get('form'):
            raise UserError(_("Form content is missing, this report cannot be printed."))

        return

    def prepare_local_ctx(self, docids, data=None):
        data = ({'form': data})
        used_context = {}

        company = self._get_company(data) or self.env.user.company_id
        data['company_id'] = company.id
        lang_code = self.env.context.get('lang') or self.env.user.lang or 'vi_VN'
        lang = self.env['res.lang']
        lang_id = lang._lang_get(lang_code)
        used_context['symbol'] = company.currency_id.symbol
        used_context['precision'] = company.currency_id.decimal_places
        used_context['position'] = company.currency_id.position
        used_context['date_format'] = lang_id.date_format
        used_context['time_format'] = lang_id.time_format

        data['form']['used_context'] = used_context
        return docids, data

    @api.model
    def action_view(self, docids, data=None):
        docids, data = self.prepare_local_ctx(docids, data)
        report_vals = self.get_report_values(docids, data)
        return json.dumps(report_vals, cls=DateTimeEncoder)

    @api.model
    def action_xlsx(self, docids, data=None):
        docids, data = self.prepare_local_ctx(docids, data)
        report_vals = self.get_report_values(docids, data)
        return report_vals

    @api.model
    def action_pdf(self, docids, data=None):
        """
        Must Override this method if you want to use.
        """
        raise NotImplementedError()

