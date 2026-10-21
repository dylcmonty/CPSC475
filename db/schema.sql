-- Almanac schema (PostgreSQL 16).
-- Twelve tables, fifteen foreign keys, two views. Matches the Stage 3
-- development plan; constraints the application reports to users are
-- named so error messages can refer to them.

-- ---------------------------------------------------------------------
-- Reference data (loaded by us, read-only for users)
-- ---------------------------------------------------------------------

CREATE TABLE observer (
    observer_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         VARCHAR(120) NOT NULL UNIQUE,
    domain       VARCHAR(255) UNIQUE,
    granularity  VARCHAR(16)  NOT NULL
                 CHECK (granularity IN ('lot', 'product_day'))
);

CREATE TABLE region (
    region_id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_region_id  INTEGER REFERENCES region (region_id),
    name              VARCHAR(120) NOT NULL,
    kind              VARCHAR(20)  NOT NULL
                      CHECK (kind IN ('country', 'state', 'county', 'other')),
    UNIQUE (parent_region_id, name),
    CHECK (parent_region_id <> region_id)
);

CREATE TABLE taxon (
    taxon_id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_taxon_id  INTEGER REFERENCES taxon (taxon_id),
    path             VARCHAR(512) NOT NULL UNIQUE,
    depth            SMALLINT     NOT NULL CHECK (depth BETWEEN 0 AND 11),
    rank             VARCHAR(20)  NOT NULL,
    scientific_name  VARCHAR(200) NOT NULL,
    common_name      VARCHAR(200),
    CHECK (parent_taxon_id <> taxon_id)
);
CREATE INDEX ix_taxon_parent ON taxon (parent_taxon_id);

CREATE TABLE product (
    product_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug        VARCHAR(80)  NOT NULL UNIQUE CHECK (slug = LOWER(slug)),
    title       VARCHAR(200) NOT NULL,
    taxon_id    INTEGER REFERENCES taxon (taxon_id) ON DELETE RESTRICT
);
CREATE INDEX ix_product_taxon ON product (taxon_id);

CREATE TABLE product_alias (
    label_norm    VARCHAR(255) PRIMARY KEY,
    product_id    INTEGER   NOT NULL
                  REFERENCES product (product_id) ON DELETE CASCADE,
    match_rung    SMALLINT  NOT NULL CHECK (match_rung BETWEEN 0 AND 4),
    confirmed_at  TIMESTAMP NOT NULL
);
CREATE INDEX ix_alias_product ON product_alias (product_id);

CREATE TABLE market_lot (
    lot_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observer_id  INTEGER NOT NULL
                 REFERENCES observer (observer_id) ON DELETE RESTRICT,
    sale_date    DATE    NOT NULL CHECK (sale_date >= DATE '2019-01-01'),
    raw_label    VARCHAR(255) NOT NULL,
    label_norm   VARCHAR(255) NOT NULL,
    unit         VARCHAR(40),
    quantity     NUMERIC(10,2) CHECK (quantity > 0),
    low_cents    INTEGER CHECK (low_cents  >= 0),
    high_cents   INTEGER CHECK (high_cents >= 0),
    avg_cents    INTEGER CHECK (avg_cents  >= 0),
    CHECK (low_cents <= high_cents),
    CHECK (avg_cents BETWEEN low_cents AND high_cents)
);
CREATE INDEX ix_lot_label    ON market_lot (label_norm);
CREATE INDEX ix_lot_date     ON market_lot (sale_date);
CREATE INDEX ix_lot_obs_date ON market_lot (observer_id, sale_date);

CREATE TABLE market_lot_quarantine (
    quarantine_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observer_id     INTEGER NOT NULL
                    REFERENCES observer (observer_id) ON DELETE RESTRICT,
    sale_date       DATE    NOT NULL,
    raw_label       VARCHAR(255) NOT NULL,
    unit            VARCHAR(40),
    quantity        NUMERIC(10,2),
    low_cents       INTEGER,
    high_cents      INTEGER,
    avg_cents       INTEGER,
    reason          VARCHAR(255) NOT NULL,
    quarantined_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE event_kind (
    event_kind_code  VARCHAR(20) PRIMARY KEY,
    label            VARCHAR(60) NOT NULL UNIQUE,
    is_yield         BOOLEAN     NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------------
-- Grower data (created, changed and deleted through the application)
-- ---------------------------------------------------------------------

CREATE TABLE farm (
    farm_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    domain       VARCHAR(255) CONSTRAINT farm_domain_unique UNIQUE,
    region_id    INTEGER NOT NULL
                 REFERENCES region (region_id) ON DELETE RESTRICT,
    owner_email  VARCHAR(255) CONSTRAINT farm_owner_email_unique UNIQUE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_farm_region ON farm (region_id);

CREATE TABLE plot (
    plot_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    farm_id    INTEGER NOT NULL
               REFERENCES farm (farm_id) ON DELETE CASCADE,
    name       VARCHAR(100) NOT NULL,
    area_sq_m  NUMERIC(10,2) CONSTRAINT plot_area_positive CHECK (area_sq_m > 0),
    CONSTRAINT plot_name_unique UNIQUE (farm_id, name)
);

CREATE TABLE crop_catalog (
    farm_id   INTEGER NOT NULL
              REFERENCES farm (farm_id) ON DELETE CASCADE,
    taxon_id  INTEGER NOT NULL
              CONSTRAINT crop_catalog_taxon_fk
              REFERENCES taxon (taxon_id) ON DELETE RESTRICT,
    added_on  DATE NOT NULL DEFAULT CURRENT_DATE,
    notes     VARCHAR(500),
    PRIMARY KEY (farm_id, taxon_id)
);

CREATE TABLE farm_event (
    event_id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    farm_id          INTEGER NOT NULL
                     REFERENCES farm (farm_id) ON DELETE CASCADE,
    plot_id          INTEGER
                     REFERENCES plot (plot_id) ON DELETE SET NULL,
    taxon_id         INTEGER NOT NULL
                     CONSTRAINT farm_event_taxon_fk
                     REFERENCES taxon (taxon_id) ON DELETE RESTRICT,
    event_kind_code  VARCHAR(20) NOT NULL
                     REFERENCES event_kind (event_kind_code) ON DELETE RESTRICT,
    product_id       INTEGER
                     REFERENCES product (product_id) ON DELETE SET NULL,
    event_date       DATE NOT NULL,
    quantity         NUMERIC(10,2)
                     CONSTRAINT farm_event_quantity_nonneg CHECK (quantity >= 0),
    unit             VARCHAR(40),
    notes            VARCHAR(1000),
    CONSTRAINT farm_event_unit_required CHECK (quantity IS NULL OR unit IS NOT NULL)
);
CREATE INDEX ix_event_farm_date ON farm_event (farm_id, event_date);
CREATE INDEX ix_event_taxon     ON farm_event (taxon_id);

-- ---------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------

-- Auction lots that resolve to a product, with prices in dollars.
CREATE VIEW v_priced_lot AS
SELECT l.lot_id, l.sale_date, o.name AS source,
       p.product_id, p.title, p.taxon_id,
       l.unit, l.quantity,
       l.low_cents / 100.0 AS low_price,
       l.high_cents / 100.0 AS high_price,
       l.avg_cents / 100.0 AS avg_price
FROM market_lot l
JOIN observer o       ON o.observer_id = l.observer_id
JOIN product_alias a  ON a.label_norm = l.label_norm
JOIN product p        ON p.product_id = a.product_id;

-- Share of auction lots matched to a product, per source.
CREATE VIEW v_resolution_coverage AS
SELECT o.name AS source,
       COUNT(*) AS total_lots,
       COUNT(a.label_norm) AS resolved_lots,
       ROUND(100.0 * COUNT(a.label_norm) / COUNT(*), 1) AS pct_resolved
FROM market_lot l
JOIN observer o ON o.observer_id = l.observer_id
LEFT JOIN product_alias a ON a.label_norm = l.label_norm
GROUP BY o.name;
