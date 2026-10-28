# Entity Relationship Diagram

The Almanac database as defined in [`db/schema.sql`](db/schema.sql): 12 tables and 15 foreign keys.

```mermaid
erDiagram
    %% Reference data (loaded by us, read-only for users)
    observer {
        int observer_id PK
        varchar name UK
        varchar domain UK
        varchar granularity "lot or product_day"
    }
    region {
        int region_id PK
        int parent_region_id FK "null for the top region"
        varchar name "unique within parent"
        varchar kind "country, state, county, other"
    }
    taxon {
        int taxon_id PK
        int parent_taxon_id FK "null for the root"
        varchar path UK
        smallint depth "0 to 11"
        varchar rank
        varchar scientific_name
        varchar common_name
    }
    product {
        int product_id PK
        varchar slug UK "lowercase"
        varchar title
        int taxon_id FK
    }
    product_alias {
        varchar label_norm PK
        int product_id FK
        smallint match_rung "0 to 4"
        timestamp confirmed_at
    }
    market_lot {
        int lot_id PK
        int observer_id FK
        date sale_date "2019 or later"
        varchar raw_label
        varchar label_norm "matched to product_alias"
        varchar unit
        numeric quantity "greater than 0"
        int low_cents "low <= avg <= high"
        int high_cents
        int avg_cents
    }
    market_lot_quarantine {
        int quarantine_id PK
        int observer_id FK
        date sale_date
        varchar raw_label
        varchar unit
        numeric quantity
        int low_cents
        int high_cents
        int avg_cents
        varchar reason
        timestamp quarantined_at
    }
    event_kind {
        varchar event_kind_code PK
        varchar label UK
        boolean is_yield
    }

    %% Grower data (insert, update and delete through the app)
    farm {
        int farm_id PK
        varchar name
        varchar domain UK
        int region_id FK
        varchar owner_email UK
        timestamp created_at
    }
    plot {
        int plot_id PK
        int farm_id FK
        varchar name "unique within farm"
        numeric area_sq_m "greater than 0"
    }
    crop_catalog {
        int farm_id PK, FK
        int taxon_id PK, FK
        date added_on
        varchar notes
    }
    farm_event {
        int event_id PK
        int farm_id FK
        int plot_id FK "optional"
        int taxon_id FK
        varchar event_kind_code FK
        int product_id FK "optional"
        date event_date
        numeric quantity "0 or more, unit required if set"
        varchar unit
        varchar notes
    }

    region         |o--o{ region                : "contains"
    taxon          |o--o{ taxon                 : "parent of"
    taxon          |o--o{ product               : "classifies"
    product        ||--o{ product_alias         : "known as"
    observer       ||--o{ market_lot            : "reports"
    observer       ||--o{ market_lot_quarantine : "reports"
    product_alias  |o..o{ market_lot            : "matches label_norm"
    region         ||--o{ farm                  : "locates"
    farm           ||--o{ plot                  : "has"
    farm           ||--o{ crop_catalog          : "grows"
    taxon          ||--o{ crop_catalog          : "listed in"
    farm           ||--o{ farm_event            : "records"
    plot           |o--o{ farm_event            : "location of"
    taxon          ||--o{ farm_event            : "crop of"
    event_kind     ||--o{ farm_event            : "kind of"
    product        |o--o{ farm_event            : "sold as"
```

Solid lines are foreign keys. The dotted line from `product_alias` to `market_lot` is a join on `label_norm`, not a foreign key: lots are loaded before their labels are matched, so a lot can have no alias yet. Those lots stay out of `v_priced_lot` until a match is confirmed.

## What Prevents Duplicates

| Table | Unique key | Stops |
| --- | --- | --- |
| `observer` | `name`, `domain` | The same auction source loaded twice |
| `region` | `(parent_region_id, name)` | Two counties with the same name in one state |
| `taxon` | `path` | The same plant twice in the taxonomy |
| `product` | `slug` | Two products with the same name |
| `product_alias` | `label_norm` (primary key) | One auction label pointing to two products |
| `event_kind` | `label` | Two event kinds with the same name |
| `farm` | `domain` (`farm_domain_unique`), `owner_email` (`farm_owner_email_unique`) | Two farms with the same website or owner |
| `plot` | `(farm_id, name)` (`plot_name_unique`) | Two plots with the same name on one farm |
| `crop_catalog` | `(farm_id, taxon_id)` (primary key) | The same crop listed twice for one farm |

Every numeric ID (`farm_id`, `plot_id`, `event_id` and the rest) is `GENERATED ALWAYS AS IDENTITY`, so the database assigns it and users cannot supply or reuse one.

## Views

| View | Joins | Purpose |
| --- | --- | --- |
| `v_priced_lot` | `market_lot`, `observer`, `product_alias`, `product` | Matched auction lots with prices in dollars |
| `v_resolution_coverage` | `market_lot`, `observer`, left join `product_alias` | Share of lots matched to a product, per source |
