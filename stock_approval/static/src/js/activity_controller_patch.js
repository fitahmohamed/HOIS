
/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityController } from "@mail/views/web/activity/activity_controller";

patch(ActivityController.prototype, {
    async openRecord(record, { newWindow } = {}) {
        if (this.props.resModel === "stock.quant" && !newWindow) {
            const rows = await this.model.orm.read(
                "stock.quant",
                [record.resId],
                ["sia_status"]
            );

            if (rows.length && rows[0].sia_status === "awaiting") {
                const action = await this.model.orm.call(
                    "stock.quant",
                    "action_sia_open_approval_list",
                    [[record.resId]]
                );

                return this.action.doAction(action);
            }
        }

        return super.openRecord(record, { newWindow });
    },
});
