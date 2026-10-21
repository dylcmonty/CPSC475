-- Controlled vocabulary the application needs before any data is loaded.
-- Reference data (taxonomy, products, market lots, farms, regions) is
-- loaded separately with scripts/import_sqlite.py.

INSERT INTO event_kind (event_kind_code, label, is_yield) VALUES
    ('plant',   'Planting', FALSE),
    ('harvest', 'Harvest',  TRUE),
    ('sale',    'Sale',     FALSE),
    ('loss',    'Loss',     FALSE)
ON CONFLICT (event_kind_code) DO NOTHING;
