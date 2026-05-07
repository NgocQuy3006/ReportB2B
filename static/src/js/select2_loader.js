/** @odoo-module **/

import { loadJS } from "@web/core/assets";

let select2Promise = null;

export async function ensureSelect2() {
    if (!select2Promise) {
        select2Promise = (async () => {
            if (!window.jQuery && !window.$) {
                await loadJS("/web/static/lib/jquery/jquery.js");
            }

            window.$ = window.jQuery || window.$;
            window.jQuery = window.jQuery || window.$;

            if (!window.$?.fn?.select2) {
                await loadJS("/b2b_base_report/static/src/js/select2.full.min.js");
            }

            return window.$;
        })().catch((error) => {
            select2Promise = null;
            console.error("Failed to load jQuery/Select2:", error);
            throw error;
        });
    }

    return select2Promise;
}

ensureSelect2();
