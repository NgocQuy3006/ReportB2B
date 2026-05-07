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
export class ProductRegistersUserFilters extends Component {
    static template = "b2b_base_report.ProductRegistersUserFilters";

    // companySelectRef = useRef("companySelect");
    // categorySelectRef = useRef("categorySelect");

    setup() {
        // 🔹 Phải khai báo toàn bộ useRef trong setup()
        this.companySelectRef = useRef("companySelect");
        this.categorySelectRef = useRef("categorySelect");
        this.productTypeRef = useRef("typeSelect");
        this.activeRef = useRef("activeCheck");
        this.inactiveRef = useRef("inactiveCheck");
        this.showAttrRef = useRef("showAttrCheck");

        onMounted(() => {
            // Delay nhỏ để đảm bảo DOM Select2 mount xong
            setTimeout(() => {
                const refs = {
                    companySelect: this.companySelectRef?.el,
                    categorySelect: this.categorySelectRef?.el,
                    typeSelect: this.productTypeRef?.el,
                    activeCheck: this.activeRef?.el,
                    inactiveCheck: this.inactiveRef?.el,
                    showAttrCheck: this.showAttrRef?.el,
                };

                console.log("✅ [UserFilters] refs ready:", refs);

                window.dispatchEvent(
                    new CustomEvent("b2b:filters-ready", { detail: refs })
                );
            }, 0);
        });
    }
    _collectFilters() {
        if (
            !this.companySelectRef?.el ||
            !this.categorySelectRef?.el ||
            !this.productTypeRef?.el ||
            !this.activeRef?.el ||
            !this.inactiveRef?.el ||
            !this.showAttrRef?.el
        ) {
            console.warn("⚠️ [UserFilters] Some refs not ready");
            return {};
        }

        // Lấy giá trị từ Select2 + input + checkbox
        const company = window.$(this.companySelectRef.el).val();
        const categories = window.$(this.categorySelectRef.el).val() || [];
        const product_type = this.productTypeRef.el.value || "all";
        const activeCheck = this.activeRef.el.checked;
        const inactiveCheck = this.inactiveRef.el.checked;
        const showAttrCheck = this.showAttrRef.el.checked;

        // Logic Active/Inactive
        let product_flag = "all";
        if (activeCheck && !inactiveCheck) product_flag = "Active";
        else if (!activeCheck && inactiveCheck) product_flag = "Inactive";

        const filter = {
            company,
            categories,
            product_type,
            product_flag,
            is_show_attribute: !!showAttrCheck,
        };

        console.log("🧩 [UserFilters] Built filter:", filter);
        return filter;
    }

    // 📤 Áp dụng lọc
    onApply() {
        const filter = this._collectFilters();
        this.props.onApplyFilters?.(filter);
    }

    // 📦 Xuất Excel
    onExportXlsx() {
        const filter = this._collectFilters();
        this.props.onExportXlsx?.(filter);
    }
}

// ========================================================
// 📊 REPORT CONTENTS
// ========================================================
export class ProductRegistersContents extends Component {
    static template = "b2b_base_report.ProductRegistersContents";
}

// ========================================================
// 🎯 MAIN COMPONENT
// ========================================================
export class ProductRegistersMain extends Component {
    static template = "b2b_base_report.ProductRegistersMain";
    static components = {
        ProductRegistersUserFilters,
        ProductRegistersContents,
    };

    setup() {
        console.log("✅ ProductRegistersMain initialized");

        this.state = useState({
            result: null,
            parsed: { html: "" },
        });

        // ====== Services ======
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
            console.log("⏳ Waiting for UserFilters refs...");
            const refs = await this._waitForFiltersReady();
            if (!refs?.companySelect || !refs?.categorySelect)
                throw new Error("Refs missing from UserFilters");

            this.filterRefs = refs; // ✅ Lưu lại refs để dùng sau
            await this._loadData(refs);
        } catch (err) {
            console.error("❌ Bootstrap failed:", err);
            this.notification.add("Initialization failed", { type: "danger" });
        }
    }

    // ========================================================
    // 🕒 Wait for Filters Ready
    // ========================================================
    _waitForFiltersReady() {
        return new Promise((resolve) => {
            const handler = (ev) => {
                window.removeEventListener("b2b:filters-ready", handler);
                resolve(ev.detail);
            };
            window.addEventListener("b2b:filters-ready", handler, { once: true });
        });
    }

    // ========================================================
    // 🔄 Loader Control
    // ========================================================
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

            const [companies, categories] = await Promise.all([
                this.rpc("/web/dataset/call_kw", {
                    model: "res.company",
                    method: "search_read",
                    args: [[], ["id", "name"]],
                }),
                this.rpc("/web/dataset/call_kw", {
                    model: "product.category",
                    method: "search_read",
                    args: [[], ["id", "name"]],
                }),
            ]);

            console.log(`✅ Loaded: ${companies.length} companies, ${categories.length} categories`);

            initSelect2(
                refs.companySelect,
                companies.map((c) => ({ id: c.id, text: c.name })),
                "Select Company..."
            );
            initSelect2(
                refs.categorySelect,
                categories.map((c) => ({ id: c.id, text: c.name })),
                "Select Category...",
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

    // 📊 Apply Filters → hiển thị báo cáo HTML
    /**
 * 🧩 Hàm chung: chạy report theo action (view | xlsx)
 */
    async _runReport(action, filter) {
        console.log(`🚀 [Main] Run report: ${action}`, filter);
        this._setLoading(true);

        try {
            if (action === "view") {
                // 📄 Render HTML view
                const result = await this.rpc("/web/dataset/call_kw", {
                    model: "report.product_registers",
                    method: "action_view",
                    args: [[], filter],
                });

                console.log("✅ Report HTML loaded");
                const html = result?.html || "";
                const container = document.querySelector(".B2B_ReportDataSection");
                container.replaceChildren();
                container.insertAdjacentHTML("beforeend", html);

                // ⚙️ Gắn lại sự kiện Expand/Collapse cho dòng sản phẩm
                const templates = container.querySelectorAll(".template-row");
                templates.forEach((row) => {
                    row.addEventListener("click", () => {
                        const id = row.getAttribute("data-id");
                        container
                            .querySelectorAll(`.variant-of-${id}`)
                            .forEach((child) => child.classList.toggle("show"));
                    });
                });

                window.expandAllVariants = () => {
                    container.querySelectorAll(".variant-row").forEach((el) => el.classList.add("show"));
                };
                window.collapseAllVariants = () => {
                    container.querySelectorAll(".variant-row").forEach((el) => el.classList.remove("show"));
                };

                this.notification.add("Report loaded successfully", { type: "success" });
            }

            // 📦 Export Excel
            else if (action === "xlsx") {
                const result = await this.rpc("/web/dataset/call_kw", {
                    model: "report.product_registers",
                    method: "action_xlsx",
                    args: [],
                    kwargs: { filters: filter }, // ✅ DÙNG kwargs
                });

                if (!result || !result.data) throw new Error("No Excel data received");

                // 🔄 Decode base64 → Blob Excel
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
                link.download = result.name || "product_registers.xlsx";
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




    // ========================================================
    // 🧰 Helper: Collect Filters (đã sửa dùng this.filterRefs)
    // ========================================================
    _collectFilters() {
        const companySelect = this.refs?.companySelect;
        const categorySelect = this.refs?.categorySelect;
        const typeSelect = document.querySelector('[t-ref="typeSelect"]');
        const activeCheck = document.querySelector('[t-ref="activeCheck"]');
        const inactiveCheck = document.querySelector('[t-ref="inactiveCheck"]');
        const showAttrCheck = document.querySelector('[t-ref="showAttrCheck"]');

        // 🧩 Company
        const company = window.$(companySelect).val();

        // 🧩 Categories (multi)
        const categories = window.$(categorySelect).val() || [];

        // 🧩 Product Type
        const product_type = typeSelect?.value || "all";

        // 🧩 Active / Inactive logic
        let product_flag = "all";
        if (activeCheck?.checked && !inactiveCheck?.checked) product_flag = "Active";
        else if (!activeCheck?.checked && inactiveCheck?.checked) product_flag = "Inactive";

        // 🧩 Show Attributes
        const is_show_attribute = !!showAttrCheck?.checked;

        const filter = {
            company,
            categories,
            product_type,
            product_flag,
            is_show_attribute,
        };

        console.log("🧾 Filters collected:", filter);
        return filter;
    }

}

// ========================================================
// 🔧 Register Client Action
// ========================================================
registry.category("actions").add("product_registers_report", ProductRegistersMain);
