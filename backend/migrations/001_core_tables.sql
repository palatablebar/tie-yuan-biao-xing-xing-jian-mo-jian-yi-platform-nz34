-- 核心表结构参考（运行时由 SQLAlchemy create_all 建表；本文件仅供 reviewer 对照字段）

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(160) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(80)  NOT NULL,
    role            VARCHAR(20)  NOT NULL,
    org             VARCHAR(120),
    created_at      TIMESTAMP    NOT NULL
);

CREATE TABLE source_tables (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(80)  NOT NULL UNIQUE,
    cn_name         VARCHAR(120) NOT NULL,
    subject         VARCHAR(40)  NOT NULL,
    domain          VARCHAR(20)  NOT NULL,
    row_count       INTEGER      NOT NULL DEFAULT 0,
    field_count     INTEGER      NOT NULL DEFAULT 0,
    sample_rows     JSON,
    note            TEXT,
    scanned_at      TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL
);

CREATE TABLE column_profiles (
    id              SERIAL PRIMARY KEY,
    table_id        INTEGER      NOT NULL REFERENCES source_tables(id) ON DELETE CASCADE,
    column_name     VARCHAR(80)  NOT NULL,
    dtype           VARCHAR(16)  NOT NULL,
    unique_ratio    DOUBLE PRECISION NOT NULL DEFAULT 0,
    null_ratio      DOUBLE PRECISION NOT NULL DEFAULT 0,
    cardinality     INTEGER      NOT NULL DEFAULT 0,
    sample_values   JSON,
    sample_size     INTEGER      NOT NULL DEFAULT 0,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_profiles_table_column UNIQUE (table_id, column_name)
);

CREATE TABLE relations (
    id              SERIAL PRIMARY KEY,
    left_table_id   INTEGER      NOT NULL REFERENCES source_tables(id) ON DELETE CASCADE,
    left_column     VARCHAR(80)  NOT NULL,
    right_table_id  INTEGER      NOT NULL REFERENCES source_tables(id) ON DELETE CASCADE,
    right_column    VARCHAR(80)  NOT NULL,
    containment     DOUBLE PRECISION NOT NULL DEFAULT 0,
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0,
    kind            VARCHAR(12)  NOT NULL,
    sample_size     INTEGER      NOT NULL DEFAULT 0,
    created_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_relations_edge UNIQUE (left_table_id, left_column, right_table_id, right_column)
);

CREATE TABLE model_runs (
    id               SERIAL PRIMARY KEY,
    run_no           VARCHAR(40)  NOT NULL UNIQUE,
    trigger          VARCHAR(20)  NOT NULL,
    status           VARCHAR(20)  NOT NULL,
    operator_email   VARCHAR(160) NOT NULL,
    table_count      INTEGER      NOT NULL DEFAULT 0,
    profile_count    INTEGER      NOT NULL DEFAULT 0,
    relation_count   INTEGER      NOT NULL DEFAULT 0,
    suggestion_count INTEGER      NOT NULL DEFAULT 0,
    metrics          JSON,
    log_text         TEXT,
    seed_key         VARCHAR(120) UNIQUE,
    started_at       TIMESTAMP    NOT NULL,
    finished_at      TIMESTAMP
);

CREATE TABLE model_suggestions (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER      NOT NULL REFERENCES model_runs(id) ON DELETE CASCADE,
    table_id        INTEGER      NOT NULL REFERENCES source_tables(id) ON DELETE CASCADE,
    target_name     VARCHAR(80)  NOT NULL,
    role            VARCHAR(8)   NOT NULL,
    grain           VARCHAR(200),
    joins           JSON,
    measures        JSON,
    attributes      JSON,
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0,
    status          VARCHAR(16)  NOT NULL DEFAULT 'pending',
    ddl             TEXT,
    reason          TEXT,
    adopted_by      VARCHAR(160),
    adopted_at      TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_suggestions_run_table UNIQUE (run_id, table_id)
);

CREATE TABLE audit_logs (
    id              SERIAL PRIMARY KEY,
    actor_email     VARCHAR(160) NOT NULL,
    actor_role      VARCHAR(20)  NOT NULL,
    action          VARCHAR(64)  NOT NULL,
    entity          VARCHAR(40)  NOT NULL,
    entity_id       VARCHAR(64),
    detail          JSON,
    layer           VARCHAR(16)  NOT NULL DEFAULT 'domain',
    ip              VARCHAR(64),
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL
);
