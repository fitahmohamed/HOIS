/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";



function toEnglishDigits(value) {
    if (!value) {
        return "";
    }

    return String(value)
        .replace(/[٠-٩]/g, (digit) => {
            return String("٠١٢٣٤٥٦٧٨٩".indexOf(digit));
        })
        .replace(/[۰-۹]/g, (digit) => {
            return String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit));
        });
}



function formatEnglishDate(value) {
    if (!value) {
        return "";
    }

    const result = value
        .setLocale("en")
        .toFormat("dd/MM/yyyy");

    return `\u2066${toEnglishDigits(result)}\u2069`;
}


function formatEnglishDatetime(value) {
    if (!value) {
        return "";
    }

    const result = value
        .setLocale("en")
        .toFormat("dd/MM/yyyy, HH:mm");

    return `\u2066${toEnglishDigits(result)}\u2069`;
}



patch(DateTimeField.prototype, {
    getFormattedValue(valueIndex, numeric) {
        const value = this.values[valueIndex];

        if (!value) {
            return "";
        }

        if (this.field.type === "date") {
            return formatEnglishDate(value);
        }

        return formatEnglishDatetime(value);
    },
});



const formatters = registry.category("formatters");

const originalDateFormatter = formatters.get("date");

if (originalDateFormatter) {
    const englishDateFormatter = function (value, options = {}) {
        if (!value) {
            return "";
        }

        return formatEnglishDate(value);
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

        return formatEnglishDatetime(value);
    };

    englishDatetimeFormatter.extractOptions =
        originalDatetimeFormatter.extractOptions;

    formatters.add(
        "datetime",
        englishDatetimeFormatter,
        { force: true }
    );
}