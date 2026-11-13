# 数据库迁移说明

本项目用 SQLAlchemy `Base.metadata.create_all()` 在 backend 启动时建表（见 `src/config/app.py`），
因此首次 `docker compose up` 会自动建好表，不需要额外执行迁移。

- `001_core_tables.sql`：核心表的人类可读 DDL 参考（PostgreSQL 语法），用于 reviewer 对照字段；
  运行时不执行它。
- 版本化改造后，`column_profiles` / `relations` / `model_suggestions` 都带 `version_id` 外键，
  归属 `analysis_versions`；人工采纳/驳回独立保存在只追加的 `suggestion_decisions`。
  由于演示库随容器卷重建（无跨版本存量数据），`create_all` 直接建新结构即可；
  生产环境若已有旧表，需引入 Alembic 补一份「建新表 + 数据迁移 + 切外键」的迁移脚本。
- 后续字段变更建议引入 Alembic，并在本目录按 `00x_<描述>.py` 递增。
- seed 数据只走 `backend/scripts/seed_demo.py`，不要写进 SQL。
