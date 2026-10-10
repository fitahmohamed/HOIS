
/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ActivityMenu } from "@mail/core/web/activity_menu";

patch(ActivityMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },

    async executeActivityAction(group, domain, views, context, newWindow) {
        if (group.model === "stock.quant") {
            const action = await this.orm.call(
                "stock.quant",
                "action_sia_open_approval_list",
                [[]]
            );

            return this.action.doAction(action, {
                newWindow,
                clearBreadcrumbs: true,
            });
        }

        return super.executeActivityAction(
            group,
            domain,
            views,
            context,
            newWindow
        );
    },
});
