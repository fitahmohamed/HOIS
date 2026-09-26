/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";

patch(DateTimeField.prototype, {
    getFormattedValue(valueIndex, numeric) {
        const value = this.values[valueIndex];

        if (!value) {
            return "";
        }

        if (this.field.type === "date") {
            return value
                .setLocale("en")
                .toFormat("dd MMMM yyyy");
        }

        return value
            .setLocale("en")
            .toFormat("dd MMMM yyyy, HH:mm");
    },
});


const formatters = registry.category("formatters");

const originalDateFormatter = formatters.get("date");

if (originalDateFormatter) {
    const englishDateFormatter = function (value, options = {}) {
        if (!value) {
            return "";
        }

    
        if (options.numeric) {
            return originalDateFormatter(value, options);
        }

        return value
            .setLocale("en")
            .toFormat("dd MMMM yyyy");
    };

    englishDateFormatter.extractOptions =
        originalDateFormatter.extractOptions;

    formatters.add(
        "date",
        englishDateFormatter,
        { force: true }
    );
}


const originalDatetimeFormatter = formatters.get("datetime");

if (originalDatetimeFormatter) {
    const englishDatetimeFormatter = function (value, options = {}) {
        if (!value) {
            return "";
        }

        
        if (options.numeric) {
            return originalDatetimeFormatter(value, options);
        }

        return value
            .setLocale("en")
            .toFormat("dd MMMM yyyy, HH:mm");
    };

    englishDatetimeFormatter.extractOptions =
        originalDatetimeFormatter.extractOptions;

    formatters.add(
        "datetime",
        englishDatetimeFormatter,
        { force: true }
    );
}