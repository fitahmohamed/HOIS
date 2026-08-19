# -*- coding: utf-8 -*-
"""
Migration 19.0.1.1 — Add project_duration_months, total_overhead_cost to project_project
and ensure project_overhead_line table exists.
"""


def migrate(cr, version):
    # Add missing columns to project_project
    cr.execute("""
        ALTER TABLE project_project
        ADD COLUMN IF NOT EXISTS project_duration_months DOUBLE PRECISION DEFAULT 0.0,
        ADD COLUMN IF NOT EXISTS total_overhead_cost      DOUBLE PRECISION DEFAULT 0.0;
    """)

    # Create project_overhead_line table if it doesn't exist yet
    cr.execute("""
        CREATE TABLE IF NOT EXISTS project_overhead_line (
            id          SERIAL PRIMARY KEY,
            project_id  INTEGER REFERENCES project_project(id) ON DELETE CASCADE,
            type_id     INTEGER,
            name        VARCHAR NOT NULL DEFAULT '',
            category    VARCHAR NOT NULL DEFAULT 'other',
            uom_name    VARCHAR,
            qty         DOUBLE PRECISION DEFAULT 1.0,
            unit_price  DOUBLE PRECISION DEFAULT 0.0,
            amount      DOUBLE PRECISION DEFAULT 0.0,
            create_uid  INTEGER,
            write_uid   INTEGER,
            create_date TIMESTAMP,
            write_date  TIMESTAMP
        );
    """)
