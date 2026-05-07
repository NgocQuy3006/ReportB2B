/** @odoo-module **/

import { Component, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ensureSelect2 } from "@b2b_base_report/js/select2_loader";

// ========================================================
// 🧩 Helper
// ========================================================
function initSelect2(el, data, placeholder, multiple = false) {
    if (!el || !window.$ || !window.$.fn.select2) return;
    const $el = window.$(el);

    if ($el.data("select2")) $el.select2("destroy");

    $el.select2({
        data,
        width: "100%",
        multiple,
        placeholder,
        allowClear: true,
        dropdownParent: window.$("body"),
        minimumResultsForSearch: Infinity, // ẩn ô search khi ít dữ liệu
    });

    // 🔒 Ngăn tự động mở dropdown khi vừa load
    setTimeout(() => $el.select2("close"), 100);

    return $el;
}

// ========================================================
// 🎛️ USER FILTERS
// ========================================================
export class PartnerRegistersUserFilters extends Component {
    static template = "b2b_base_report.PartnerRegistersUserFilters";

    setup() {
        this.companySelectRef = useRef("companySelect");
        this.partnerTypeRef = useRef("typeSelect");
        this.tagSelectRef = useRef("tagSelect");
        this.activeRef = useRef("activeCheck");
        this.inactiveRef = useRef("inactiveCheck");

        onMounted(() => {
            setTimeout(() => {
                const refs = {
                    companySelect: this.companySelectRef?.el,
                    typeSelect: this.partnerTypeRef?.el,
                    tagSelect: this.tagSelectRef?.el,
                    activeCheck: this.activeRef?.el,
                    inactiveCheck: this.inactiveRef?.el,
                };
                console.log("✅ [PartnerFilters] refs ready:", refs);
                window.dispatchEvent(
                    new CustomEvent("b2b:partner-filters-ready", { detail: refs })
                );
            }, 0);
        });
    }

    _collectFilters() {
        if (
            !this.companySelectRef?.el ||
            !this.partnerTypeRef?.el ||
            !this.tagSelectRef?.el ||
            !this.activeRef?.el ||
            !this.inactiveRef?.el
        ) {
            console.warn("⚠️ [PartnerFilters] Some refs not ready");
            return {};
        }

        // Lấy giá trị từ Select2 + checkbox
        const company = window.$(this.companySelectRef.el).val();
        const partner_type = this.partnerTypeRef.el.value || "all";
        const tags = window.$(this.tagSelectRef.el).val() || [];

        const activeCheck = this.activeRef.el.checked;
        const inactiveCheck = this.inactiveRef.el.checked;

        let activate_flag = "all";
        if (activeCheck && !inactiveCheck) activate_flag = "Active";
        else if (!activeCheck && inactiveCheck) activate_flag = "Inactive";

        const filter = {
            company,
            partner_type,
            tags,
            activate_flag,
        };
        console.log("🧩 [PartnerFilters] Built filter:", filter);
        return filter;
    }

    onApply() {
        const filter = this._collectFilters();
        this.props.onApplyFilters?.(filter);
    }

    onExportXlsx() {
        const filter = this._collectFilters();
        this.props.onExportXlsx?.(filter);
    }
}

// ========================================================
// 📊 REPORT CONTENTS
// ========================================================
export class PartnerRegistersContents extends Component {
    static template = "b2b_base_report.PartnerRegistersContents";
}

// ========================================================
// 🎯 MAIN COMPONENT
// ========================================================
export class PartnerRegistersMain extends Component {
    static template = "b2b_base_report.PartnerRegistersMain";
    static components = {
        PartnerRegistersUserFilters,
        PartnerRegistersContents,
    };

    setup() {
        console.log("✅ PartnerRegistersMain initialized");

        this.state = useState({
            result: null,
            parsed: { html: "" },
        });

        try {
            this.rpc = useService("rpc");
        } catch {
            const env = this.env;
            this.rpc = async (route, params) => {
                if (env?.services?.rpc) return env.services.rpc(route, params);
                if (env?.services?.orm)
                    return env.services.orm.call(
                        params.model,
                        params.method,
                        params.args || [],
                        params.kwargs || {}
                    );
                throw new Error("RPC service unavailable in this context.");
            };
        }

        try {
            this.notification = useService("notification");
        } catch {
            this.notification = {
                add: (msg, opts) => console.log(`[NOTIFY:${opts?.type}] ${msg}`),
            };
        }

        try {
            this.action = useService("action");
        } catch {
            this.action = { doAction: (a) => console.log("Action executed:", a) };
        }

        onMounted(() => this._bootstrapSafely());
    }

    // ========================================================
    // 🚀 Bootstrap Flow
    // ========================================================
    async _bootstrapSafely() {
        try {
            console.log("⏳ Waiting for PartnerFilters refs...");
            const refs = await this._waitForFiltersReady();
            if (!refs?.companySelect || !refs?.typeSelect)
                throw new Error("Refs missing from UserFilters");
            this.filterRefs = refs;
            await this._loadData(refs);
        } catch (err) {
            console.error("❌ Bootstrap failed:", err);
            this.notification.add("Initialization failed", { type: "danger" });
        }
    }

    _waitForFiltersReady() {
        return new Promise((resolve) => {
            const handler = (ev) => {
                window.removeEventListener("b2b:partner-filters-ready", handler);
                resolve(ev.detail);
            };
            window.addEventListener("b2b:partner-filters-ready", handler, { once: true });
        });
    }

    _setLoading(show) {
        const loader = this.refs?.loader;
        if (loader) loader.style.visibility = show ? "visible" : "hidden";
    }

    // ========================================================
    // 📦 Load Dropdown Data
    // ========================================================
    async _loadData(refs) {
        try {
            this._setLoading(true);
            await ensureSelect2();

            const [companies, tags] = await Promise.all([
                this.rpc("/web/dataset/call_kw", {
                    model: "res.company",
                    method: "search_read",
                    args: [[], ["id", "name"]],
                }),
                this.rpc("/web/dataset/call_kw", {
                    model: "res.partner.category",
                    method: "search_read",
                    args: [[], ["id", "name"]],
                }),
            ]);

            console.log(`✅ Loaded: ${companies.length} companies, ${tags.length} tags`);

            initSelect2(
                refs.companySelect,
                companies.map((c) => ({ id: c.id, text: c.name })),
                "Select Company..."
            );
            initSelect2(
                refs.tagSelect,
                tags.map((t) => ({ id: t.id, text: t.name })),
                "Select Partner Tags...",
                true
            );

            this.notification.add("Filters loaded successfully", { type: "success" });
        } catch (err) {
            console.error("❌ Error loading data:", err);
            this.notification.add("Failed to load filter data", { type: "danger" });
        } finally {
            this._setLoading(false);
        }
    }

    // ========================================================
    // 🧭 UI Handlers
    // ========================================================
    async _runReport(action, filter) {
        console.log(`🚀 [PartnerMain] Run report: ${action}`, filter);
        this._setLoading(true);

        try {
            if (action === "view") {
                const result = await this.rpc("/web/dataset/call_kw", {
                    model: "report.partner_registers",
                    method: "action_view",
                    args: [[], filter],
                });

                console.log("✅ Partner report HTML loaded");
                const html = result?.html || "";
                const container = document.querySelector(".B2B_ReportDataSection");
                container.replaceChildren();
                container.insertAdjacentHTML("beforeend", html);

                this.notification.add("Report loaded successfully", { type: "success" });
            } else if (action === "xlsx") {
                const result = await this.rpc("/web/dataset/call_kw", {
                    model: "report.partner_registers",
                    method: "action_xlsx",
                    args: [],
                    kwargs: { filters: filter },
                });

                if (!result || !result.data) throw new Error("No Excel data received");

                const byteChars = atob(result.data);
                const byteArray = new Uint8Array(byteChars.length);
                for (let i = 0; i < byteChars.length; i++) {
                    byteArray[i] = byteChars.charCodeAt(i);
                }
                const blob = new Blob([byteArray], {
                    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                });

                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = result.name || "partner_registers.xlsx";
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(link.href);

                this.notification.add("✅ Excel exported successfully", { type: "success" });
            }
        } catch (err) {
            console.error(`❌ Error running ${action}:`, err);
            const msg = action === "xlsx" ? "Failed to export Excel" : "Failed to load report";
            this.notification.add(msg, { type: "danger" });
        } finally {
            this._setLoading(false);
        }
    }

    onApply(filter) {
        this._runReport("view", filter);
    }

    onExportXlsx(filter) {
        this._runReport("xlsx", filter);
    }
}

// ========================================================
// 🔧 Register Client Action
// ========================================================
registry.category("actions").add("partner_registers_report", PartnerRegistersMain);
