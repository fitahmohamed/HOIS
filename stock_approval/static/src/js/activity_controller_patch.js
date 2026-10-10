
/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityController } from "@mail/views/web/activity/activity_controller";

patch(ActivityController.prototype, {
    async openRecord(record, { newWindow } = {}) {
        console.log("[stock_approval] openRecord called", {
            resModel: this.props.resModel,
            resId: record.resId,
            newWindow,
        });

        if (this.props.resModel === "stock.quant" && !newWindow) {
            try {
                const rows = await this.model.orm.read(
                    "stock.quant",
                    [record.resId],
                    ["sia_status"]
                );

                console.log("[stock_approval] quant status", rows);

                if (rows.length && rows[0].sia_status === "awaiting") {
                    const action = await this.model.orm.call(
                        "stock.quant",
                        "action_sia_open_approval_list",
                        [[record.resId]]
                    );

                    console.log("[stock_approval] opening approval action", action);
                    return this.action.doAction(action);
                }
            } catch (error) {
                console.error("[stock_approval] Failed to open approval action", error);
                throw error;
            }
        }

        return super.openRecord(record, { newWindow });
    },
});
