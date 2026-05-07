# -*- coding: utf-8 -*-
# Author: Lã Tuấn Kiệt
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, _
from io import BytesIO
import base64
import xlsxwriter
import logging

_logger = logging.getLogger(__name__)


class ReportPartnerRegisters(models.AbstractModel):
    _name = 'report.partner_registers'
    _inherit = 'report.abstract_report'
    _description = "Partner Registers - list of partners in system"

    # =====================================================
    # 🧩 CORE LOGIC
    # =====================================================
    def _get_tags_param(self, data):
        """Get list of partner tag ids from filter (supports ['1','2'] or [{'id':1},...])."""
        form = (data or {}).get('form', {}) or {}
        raw = form.get('tags') or form.get('partner_tags') or []
        ids = []
        for x in raw:
            if isinstance(x, dict) and x.get('id'):
                ids.append(int(x['id']))
            elif isinstance(x, (int, str)) and f"{x}".strip():
                try:
                    ids.append(int(x))
                except Exception:
                    continue
        return ids

    def build_query(self, data):
        """SQL for partner listing (no dependency on CRM/Account)."""
        query = """
        SELECT  a.id,
                a.ref                  AS code,
                a.nickname             AS short_name,
                a.name                 AS full_name,
                a.parent_id,
                a.street               AS address,
                a.city,
                st.name                AS province,
                c.name                 AS country,
                a.vat,
                a.phone,
                a.email,
                a.customer_rank,
                a.supplier_rank,
                a.is_company,
                pc.name                AS category,
                CASE WHEN a.active THEN 'Active' ELSE 'Inactive' END AS activate_flag
        FROM res_partner a
            LEFT JOIN res_country_state st ON a.state_id = st.id
            LEFT JOIN res_country c        ON a.country_id = c.id
            LEFT JOIN res_partner_res_partner_category_rel r ON a.id = r.partner_id
            LEFT JOIN res_partner_category pc ON r.category_id = pc.id
        WHERE 1 = %s
        """
        params = [1]

        form = (data or {}).get('form', {}) or {}

        # Active / Inactive
        flag = form.get('activate_flag')
        if flag == 'Active':
            query += " AND a.active = true"
        elif flag == 'Inactive':
            query += " AND a.active = false"

        # Partner type
        ptype = form.get('partner_type', 'all')
        if ptype == 'all':
            query += " AND (a.customer_rank > 0 OR a.supplier_rank > 0)"
        elif ptype == 'customer':
            query += " AND a.customer_rank > 0"
        elif ptype == 'supplier':
            query += " AND a.supplier_rank > 0"

        # Tags
        tag_ids = self._get_tags_param(data)
        if tag_ids:
            query += " AND pc.id IN %s"
            params.append(tuple(tag_ids))

        return query, params

    @api.model
    def get_report_values(self, docids, data=None):
        """Standard report render backend (language handled by Odoo usual rules)."""
        user_lang = self.env.user.lang or "en_US"

        query, params = self.build_query(data)
        self.env.cr.execute(query, tuple(params))
        partners = self.env.cr.dictfetchall()

        # 🔧 Normalize function (same as product)
        def _normalize(value):
            if isinstance(value, dict):
                if user_lang in value and value[user_lang]:
                    return value[user_lang]
                return next(iter(value.values()), "")
            return value or ""

        # Apply normalization to every record
        for rec in partners:
            for k, v in rec.items():
                rec[k] = _normalize(v)

        # split company vs contacts
        companies = sorted(
            [r for r in partners if not r.get('parent_id')],
            key=lambda x: (x.get('code') or '', x.get('full_name') or '')
        )

        lines = []
        for com in companies:
            children = [r for r in partners if r.get('parent_id') == com['id']]
            if children:
                com['main_id'] = f"line{com['id']}"
                com['has_children'] = True
                for ch in children:
                    ch['parent'] = f"line{com['id']}"
                com['children'] = children
            else:
                com['has_children'] = False
                com['children'] = []
            lines.append(com)

        return {'data': data, 'lines': lines}

    # =====================================================
    # 🧩 OWL INTERFACE FOR FRONTEND (HTML)
    # =====================================================
    @api.model
    def action_view(self, docids=None, filters=None):
        """Return professional bordered HTML (same pattern as product report)."""
        data = {'form': filters or {}}
        res = self.get_report_values(docids or [], data)
        lines = res.get('lines', [])

        title = _("Partner Registers Report")
        btn_expand = _("Expand")
        btn_collapse = _("Collapse")
        msg_no_data_title = _("No partners found.")
        msg_no_data_hint = _("Try adjusting your filters and reapply.")
        partners_found = _("partners found")

        if not lines:
            return {
                "html": f"""
                <link rel="stylesheet" href="/b2b_base_report/static/src/css/report_theme.css"/>
                <div class="alert alert-light text-center py-5 mb-0">
                    <i class="fa fa-users text-secondary fa-2x mb-2"></i><br/>
                    <strong>{msg_no_data_title}</strong><br/>
                    <span class="text-muted">{msg_no_data_hint}</span>
                </div>
                """
            }

        # Build table rows
        html_rows = []
        for idx, line in enumerate(lines, start=1):
            children_html = ""
            if line.get("children"):
                for child in line["children"]:
                    children_html += f"""
                        <tr class="partner-contact collapse {child.get('parent')}">
                            <td class="text-end pe-2">↳</td>
                            <td>{child.get('code') or ''}</td>
                            <td>{child.get('short_name') or ''}</td>
                            <td>{child.get('full_name') or ''}</td>
                            <td>{child.get('address') or ''}</td>
                            <td>{child.get('city') or ''}</td>
                            <td>{child.get('province') or ''}</td>
                            <td>{child.get('country') or ''}</td>
                            <td>{child.get('vat') or ''}</td>
                            <td>{child.get('category') or ''}</td>
                            <td>{child.get('phone') or ''}</td>
                            <td class="text-center">{child.get('activate_flag') or ''}</td>
                        </tr>
                    """
            html_rows.append(f"""
                <tr class="partner-main" data-toggle="collapse" data-target=".line{line['id']}">
                    <td class="text-end pe-2 fw-bold">{idx}</td>
                    <td class="fw-bold text-primary">{line.get('code') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('short_name') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('full_name') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('address') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('city') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('province') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('country') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('vat') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('category') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('phone') or ''}</td>
                    <td class="fw-bold text-primary">{line.get('mobile') or ''}</td>
                    <td class="text-center fw-bold">{line.get('activate_flag') or ''}</td>
                </tr>
                {children_html}
            """)

        html = f"""
        <link rel="stylesheet" href="/b2b_base_report/static/src/css/report_theme.css"/>

        <div class="card shadow-sm">
            <div class="card-header">
                <h5 class="mb-0"><i class="fa fa-users me-2"></i> {title}</h5>
                <div class="d-flex align-items-center gap-2">
                    <small class="ms-2 opacity-75">{len(lines)} {partners_found}</small>
                </div>
            </div>

            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-bordered align-middle mb-0">
                        <thead class="text-center text-nowrap">
                            <tr>
                                <th class="text-end" style="width: 40px;">#</th>
                                <th style="width: 110px;">Code</th>
                                <th style="width: 140px;">Short Name</th>
                                <th>Full Name</th>
                                <th style="width: 180px;">Address</th>
                                <th style="width: 120px;">City</th>
                                <th style="width: 120px;">Province</th>
                                <th style="width: 120px;">Country</th>
                                <th style="width: 140px;">Tax Registry</th>
                                <th style="width: 160px;">Category</th>
                                <th style="width: 120px;">Phone</th>
                                <th style="width: 120px;">Mobile</th>
                                <th style="width: 110px;">Activation</th>
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
            window.expandAllContacts = () => {{
                document.querySelectorAll(".partner-contact").forEach(el => el.classList.add("show"));
            }};
            window.collapseAllContacts = () => {{
                document.querySelectorAll(".partner-contact").forEach(el => el.classList.remove("show"));
            }};
        </script>
        """
        return {"html": html}

    # =====================================================
    # 🧩 OWL INTERFACE FOR FRONTEND (XLSX shell)
    # =====================================================
    @api.model
    def action_xlsx(self, docids=None, filters=None):
        """Return Base64 XLSX using external generator like Product report."""
        data = {"form": filters or {}}

        result = self.get_report_values(docids or [], data)
        data["lines"] = result.get("lines", [])
        data["data"] = result.get("data", data)

        _logger.info("📦 Generating Partner XLSX with %s lines", len(data["lines"]))

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        xlsx_model = self.env["report.b2b_base_report.partner_registers_xlsx"]
        xlsx_model.generate_xlsx_report(workbook, data, None)

        workbook.close()
        xlsx_data = base64.b64encode(output.getvalue()).decode("utf-8")
        output.close()
        return {"data": xlsx_data, "name": "partner_registers.xlsx"}
