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



patch(DateTimeField.prototype, {
    getFormattedValue(valueIndex, numeric) {
        const value = this.values[valueIndex];

        if (!value) {
            return "";
        }

        let result;

        if (this.field.type === "date") {
            result = value
                .setLocale("en")
                .toFormat("dd MMMM yyyy");
        } else {
            result = value
                .setLocale("en")
                .toFormat("dd MMMM yyyy, HH:mm");
        }

        return toEnglishDigits(result);
    },
});



const formatters = registry.category("formatters");

const originalDateFormatter = formatters.get("date");

if (originalDateFormatter) {

    const englishDateFormatter = function (value, options = {}) {

        if (!value) {
            return "";
        }

        const result = value
            .setLocale("en")
            .toFormat("dd MMMM yyyy");

        return toEnglishDigits(result);
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

        const result = value
            .setLocale("en")
            .toFormat("dd MMMM yyyy, HH:mm");

        return toEnglishDigits(result);
    };

    englishDatetimeFormatter.extractOptions =
        originalDatetimeFormatter.extractOptions;

    formatters.add(
        "datetime",
        englishDatetimeFormatter,
        { force: true }
    );
}