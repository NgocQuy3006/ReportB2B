# -*- coding: utf-8 -*-
# Author: Lã Tuấn Kiệt
# Copyright © 2017 B2B Technology
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, _, tools
from markupsafe import Markup
import base64
from io import BytesIO
from odoo import api, models
import xlsxwriter
import logging
_logger = logging.getLogger(__name__)

class ReportProductRegisters(models.AbstractModel):
    _name = 'report.product_registers'
    _inherit = 'report.abstract_report'
    _description = "Product Registers - list of product in system"

    # =====================================================
    # 🧩 CORE LOGIC
    # =====================================================
    def build_query(self, data):
        query = """
        SELECT t.id,
               COALESCE(t.default_code, 'No Code') AS code,
               t.short_name,
               t.name,
               u.name AS unit_uom,
               u.precision,
               CASE t.type
                    WHEN 'product' THEN 'Storable Product'
                    WHEN 'consu' THEN 'Consumable'
                    WHEN 'service' THEN 'Service'
                    ELSE t.type
               END AS product_type,
               t.categ_id,
               c.complete_name AS categ_name,
               t.list_price AS sale_price,
               t.weight,
               t.volume,
               t.sale_ok,
               t.purchase_ok,
               CASE WHEN t.active THEN 'Active' ELSE 'Inactive' END AS flag
        FROM product_template t
        LEFT JOIN product_category c ON t.categ_id = c.id
        LEFT JOIN uom_uom u ON t.uom_id = u.id
        WHERE 1 = %s
        """
        params = [1]

        form = data.get('form', {})
        if form.get('product_flag') == 'Active':
            query += " AND t.active = true"
        elif form.get('product_flag') == 'Inactive':
            query += " AND t.active = false"

        categ_ids = self._get_categories_param(data)
        if categ_ids:
            query += " AND c.id in %s"
            params += [tuple(categ_ids)]
        if form.get('product_type', 'all') != 'all':
            query += ' AND t."type" = %s'
            params += [form.get('product_type')]

        return query, params

    def _get_categories_param(self, data):
        """Get list of category ids from filter"""
        cats = data.get('form', {}).get('categories') or []
        try:
            return [int(x) for x in cats if x]
        except Exception:
            return []

    @api.model
    def get_report_values(self, docids, data=None):
        """Standard report render backend - auto pick translation by user language."""
        # Lấy ngôn ngữ user hiện tại (vd: 'vi_VN' hoặc 'en_US')
        user_lang = self.env.user.lang or 'en_US'

        context = dict(self.env.context)
        context.update({
            'lang': user_lang,
            'active_test': False,
            'allowed_company_ids': self.env.companies.ids,
        })
        product_obj = self.env['product.product'].with_context(context)
        template_obj = self.env['product.template'].with_context(context)

        query, params = self.build_query(data)
        self.env.cr.execute(query, tuple(params))
        product_templates = self.env.cr.dictfetchall()
        _logger.warning("📄 is_show_attribute in Excel: %s", data.get('form', {}).get('is_show_attribute'))

        # 🔧 Hàm normalize: ưu tiên lấy theo ngôn ngữ user, fallback sang ngôn ngữ khác
        def _normalize(value):
            if isinstance(value, dict):
                # Ưu tiên ngôn ngữ hiện tại của user
                if user_lang in value and value[user_lang]:
                    return value[user_lang]
                # Nếu không có, lấy bản dịch đầu tiên trong dict
                return next(iter(value.values()), "")
            return value or ""

        # Chuẩn hóa toàn bộ dict trả về từ SQL
        for rec in product_templates:
            for key, val in rec.items():
                rec[key] = _normalize(val)

        # Sắp xếp theo mã sản phẩm
        product_templates = sorted(product_templates, key=lambda x: x.get('code') or '')

        is_show_attribute = data.get('form', {}).get('is_show_attribute')
        lines_op = []

        for template in product_templates:
            template_id = template_obj.browse(template['id'])
            template['main_id'] = f"line{template_id.id}"
            template['cost'] = template_id.standard_price

            # 🔧 Chuẩn hóa tên và các field hiển thị
            template['name'] = _normalize(template.get('name'))
            template['unit_uom'] = _normalize(template.get('unit_uom'))
            template['categ_name'] = _normalize(template.get('categ_name'))

            # ✅ Nếu bật Show Attributes → lấy variants (product.product)
            if is_show_attribute:
                products = product_obj.search([('product_tmpl_id', '=', template_id.id)])
                children = []
                for product in products:
                    children.append({
                        'parent': f"line{template_id.id}",
                        'code': product.default_code or '',
                        'short_name': product.barcode or '',
                        'name': f"→ {product.display_name or template['name']}",
                        'unit_uom': _normalize(product.uom_id.name),
                        'categ_name': template['categ_name'],
                        'product_type': _('Variant'),
                        'cost': product.standard_price,
                        'sale_price': product.list_price,
                        'weight': product.weight,
                        'volume': product.volume,
                        'flag': 'Active' if product.active else 'Inactive',
                    })
                template['children'] = children
                template['has_children'] = bool(children)
            else:
                template['children'] = []  # 🔸 đảm bảo luôn tồn tại key, tránh lỗi KeyError

            lines_op.append(template)

        return {'data': data, 'lines': lines_op}


    # =====================================================
    # 🧩 OWL INTERFACE FOR FRONTEND
    # ===================================================

    @api.model
    def action_view(self, docids=None, filters=None):
        """Return professional bordered HTML report synced with Odoo Primary color (CSS separated)."""
        data = {'form': filters or {}}
        res = self.get_report_values(docids or [], data)
        lines = res.get('lines', [])

        # ======================
        # 🌍 Translatable Texts
        # ======================
        title = _("Product Registers Report")
        btn_expand = _("Expand")
        btn_collapse = _("Collapse")
        msg_no_data_title = _("No products found.")
        msg_no_data_hint = _("Try adjusting your filters and reapply.")
        products_found = _("products found")

        # Table headers (also translatable)
        headers = {
            "no": _("#"),
            "code": _("Code"),
            "short": _("Short Name"),
            "name": _("Name"),
            "uom": _("UoM"),
            "categ": _("Category"),
            "type": _("Type"),
            "cost": _("Cost"),
            "price": _("Sale Price"),
            "weight": _("Weight"),
            "volume": _("Volume"),
            "status": _("Status"),
        }

        # ======================
        # 🧩 Empty State
        # ======================
        if not lines:
            return {
                "html": f"""
                <link rel="stylesheet" href="/b2b_base_report/static/src/css/report_theme.css"/>

                <div class="alert alert-light text-center py-5 mb-0">
                    <i class="fa fa-box-open text-secondary fa-2x mb-2"></i><br/>
                    <strong>{msg_no_data_title}</strong><br/>
                    <span class="text-muted">{msg_no_data_hint}</span>
                </div>
                """
            }

        # ======================
        # 🧱 Build Table Rows
        # ======================
        html_rows = []
        for idx, line in enumerate(lines, start=1):
            children_html = ""
            if line.get("children"):
                for child in line["children"]:
                    status_class = "bg-success" if child.get("flag") == "Active" else "bg-secondary"
                    children_html += f"""
                        <tr class="variant-row collapse variant-of-{line['id']}">
                            <td class="text-end pe-2">↳</td>
                            <td>{child.get('code') or ''}</td>
                            <td>{child.get('short_name') or ''}</td>
                            <td>{line.get('name') or ''}</td>
                            <td>{child.get('unit_uom') or ''}</td>
                            <td>{line.get('categ_name') or ''}</td>
                            <td>{line.get('product_type') or ''}</td>
                            <td class="text-end text-danger">{child.get('cost') or 0:,.2f}</td>
                            <td class="text-end text-success">{child.get('sale_price') or 0:,.2f}</td>
                            <td class="text-end">{child.get('weight') or 0:,.3f}</td>
                            <td class="text-end">{child.get('volume') or 0:,.3f}</td>
                            <td class="text-center">
                                <span class="badge rounded-pill {status_class}">
                                    {child.get('flag') or ''}
                                </span>
                            </td>
                        </tr>
                    """

            status_class = "bg-success" if line.get("flag") == "Active" else "bg-secondary"
            html_rows.append(f"""
                <tr class="template-row" data-id="{line['id']}">
                    <td class="text-end pe-2 fw-bold">{idx}</td>
                    <td class="fw-bold text-primary">{line.get('code') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('short_name') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('name') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('unit_uom') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('categ_name') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('product_type') or ''}</td>
                    <td class="text-end text-danger fw-bold">{line.get('cost') or 0:,.2f}</td>
                    <td class="text-end text-success fw-bold">{line.get('sale_price') or 0:,.2f}</td>
                    <td class="text-end fw-bold text-primary">{line.get('weight') or 0:,.3f}</td>
                    <td class="text-end fw-bold text-primary">{line.get('volume') or 0:,.3f}</td>
                    <td class="text-center fw-bold">
                        <span class="badge rounded-pill {status_class}">
                            {line.get('flag') or ''}
                        </span>
                    </td>
                </tr>
                {children_html}
            """)

        # ======================
        # 🧩 Final HTML
        # ======================
        html = f"""
        <link rel="stylesheet" href="/b2b_base_report/static/src/css/report_theme.css"/>

        <div class="card shadow-sm">
            <div class="card-header">
                <h5><i class="fa fa-boxes me-2"></i> {title}</h5>
                <div class="d-flex align-items-center gap-2">
                    <button class="btn btn-sm btn-outline-light" onclick="expandAllVariants()">
                        <i class="fa fa-plus-square me-1"></i> {btn_expand}
                    </button>
                    <button class="btn btn-sm btn-outline-light" onclick="collapseAllVariants()">
                        <i class="fa fa-minus-square me-1"></i> {btn_collapse}
                    </button>
                    <small class="ms-2 opacity-75">{len(lines)} {products_found}</small>
                </div>
            </div>

            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-bordered align-middle mb-0">
                        <thead class="text-center text-nowrap">
                            <tr>
                                <th class="text-end" style="width: 40px;">{headers['no']}</th>
                                <th style="width: 100px;">{headers['code']}</th>
                                <th style="width: 130px;">{headers['short']}</th>
                                <th>{headers['name']}</th>
                                <th style="width: 90px;">{headers['uom']}</th>
                                <th style="width: 140px;">{headers['categ']}</th>
                                <th style="width: 130px;">{headers['type']}</th>
                                <th class="text-end" style="width: 90px;">{headers['cost']}</th>
                                <th class="text-end" style="width: 100px;">{headers['price']}</th>
                                <th class="text-end" style="width: 90px;">{headers['weight']}</th>
                                <th class="text-end" style="width: 90px;">{headers['volume']}</th>
                                <th class="text-center" style="width: 100px;">{headers['status']}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(html_rows)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script>
            // Handle expand/collapse per template row
            document.querySelectorAll(".template-row").forEach((row) => {{
                row.addEventListener("click", (ev) => {{
                    // prevent bubbling on button clicks inside the header
                    if (ev.target.closest("button")) return;
                    const id = row.getAttribute("data-id");
                    document.querySelectorAll(`.variant-of-${{id}}`).forEach((child) => {{
                        child.classList.toggle("show");
                    }});
                }});
            }});

            // Global expand/collapse
            window.expandAllVariants = () => {{
                document.querySelectorAll(".variant-row").forEach((el) => el.classList.add("show"));
            }};
            window.collapseAllVariants = () => {{
                document.querySelectorAll(".variant-row").forEach((el) => el.classList.remove("show"));
            }};
        </script>
        """

        return {"html": html}


    @api.model
    def action_xlsx(self, docids=None, filters=None):
        """Called from OWL frontend → Return Base64 XLSX binary."""
        data = {"form": filters or {}}

        # 🧩 Gọi lại logic lấy dữ liệu dòng báo cáo (giống như action_view)
        result = self.get_report_values(docids or [], data)
        # Thêm 'lines' và các phần cần thiết vào data để template có thể đọc
        data["lines"] = result.get("lines", [])
        data["data"] = result.get("data", data)
        
        _logger.warning("📦 Total lines: %s", len(data["lines"]))
        for line in data["lines"]:
            _logger.warning("➡️ %s has %s children", line.get("code"), len(line.get("children") or []))

        # 📘 Tạo workbook trong bộ nhớ
        output = BytesIO()
        report_model = self.env["report.b2b_base_report.product_registers_xlsx"]
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        # 🧾 Sinh file Excel
        report_model.generate_xlsx_report(workbook, data, None)
        workbook.close()

        # 🔁 Trả về base64 cho frontend
        xlsx_data = base64.b64encode(output.getvalue()).decode("utf-8")
        output.close()

        return {
            "data": xlsx_data,
            "name": "product_registers.xlsx",
        }
