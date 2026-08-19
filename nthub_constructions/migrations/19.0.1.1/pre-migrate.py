# -*- coding: utf-8 -*-
"""Add cost_price, profit_margin, sell_price to owner_contract_line"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE owner_contract_line
        ADD COLUMN IF NOT EXISTS cost_price     NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS profit_margin  NUMERIC DEFAULT 0,
        ADD COLUMN IF NOT EXISTS sell_price     NUMERIC DEFAULT 0;
    """)
