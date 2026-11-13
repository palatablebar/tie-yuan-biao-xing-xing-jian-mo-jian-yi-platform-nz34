# 贴源表星型建模建议台（`starmodel`）

> 数仓与数据湖 · 主外键发现 + 星型建模 + DDL。原生 HTML/CSS/JS 前端 + Python FastAPI 后端 + Celery worker + MySQL + Redis，5 个容器一键起。

## 1. 场景

- **模拟客户**：禾丰零售（300 家门店）数仓组 7 人，业务库同步出 24 张贴源表（含 4 张事实候选、12 张维表、8 张无主键流水/配置表），要从贴源层建维度模型。
- **现有工作流**：建模师用 DBeaver 看表结构，靠经验猜主外键，在 draw.io 画 ER 图，再手写 `CREATE TABLE`。口径散落在个人 Excel 与聊天记录里。
- **三个痛点**：
  1. **粒度靠经验**：订单明细到底是「订单」还是「订单行 × 门店 × 商品 × 日期」，没有量化的去重计数。
  2. **维表冗余**：同一区域主档被复制进多张表，二级维与主维不分。
  3. **事实表关联错**：包含度不到 1 的「同名键」被当成主外键，指标重复统计。
- **上下游**：业务库表结构 + 抽样行 → 本系统（剖析 → 关系发现 → 星型建议 → DDL）→ 数仓开发（dbt/调度）与 BI。
- **一天的工作剧本**：09:10 数据同步把 `ods_sales_order_item` 等 24 张表登记进制图台；09:20 建模专员点「执行剖析」，后端在 0.4 秒内完成 180 个字段的唯一率/空值率/基数统计；09:25 关系图上出现 18 条包含依赖（其中 `ods_member_points.member_id` 包含度 98.3%，标为弱外键）；09:40 建议页出现 `dwd_sales_fact`，粒度「门店×商品×日期（抽样 200 行去重 120 个组合）」；10:05 管理员采纳该建议；10:10 导出 9 段 DDL 交给 dbt；10:20 审计页出现 4 条操作痕迹。

## 2. 角色与权限

| 角色 | 账号 | 权限 | 典型动作 |
|---|---|---|---|
| 平台管理员 `admin` | `admin@starmodel.io` | 表登记 + 剖析 + 采纳 + 导出 DDL + 审计 | 登记新贴源表、采纳 `dwd_sales_fact`、导出 9 段 DDL |
| 建模专员 `analyst` | `analyst@starmodel.io` | 剖析 + 查看 + 驳回 + 导出 CSV | 执行剖析、驳回弱外键建议、导出关系清单 |
| 只读访客 `viewer` | `viewer@starmodel.io` | 只读表/关系图/建议 | 看关系图与建议，不能剖析、采纳、导出 |

密码统一 `Demo@2026`。低权调用高权接口返回真实 **403**（`admin` 专属：`POST /api/source-tables`、`POST /api/model-suggestions/{id}/adopt`、`GET /api/exports/ddl.sql`、`GET /api/audit`）；未登录 **401**；参数非法 **422**；重复表名 **409**。

## 3. 功能模块（串成一条链路）

1. **贴源表与剖析**（`#/tables`）：24 张表按主题域筛选；抽屉里逐列看唯一率、空值率、基数与样本值（服务端剖析结果）。
2. **关系图**（`#/relations`）：SVG 主视觉，18 条边按「二级维 → 主维 → 事实」三带排布；点击节点高亮它的边；下方包含依赖清单可看包含度/置信度。
3. **建模建议**（`#/suggestions`）：9 条建议（4 事实 + 5 主维），含粒度、关联边、置信度、DDL；管理员采纳、专员驳回，状态落库且不被重跑覆盖。
4. **总览**（`#/overview`）：表/字段/关系/建议计数、关系类型与建议状态分布、最近一次剖析指标与日志、7 日趋势。
5. **导出与审计**：管理员导出 `ddl.sql`（9 段）、专员导出关系 CSV；登录/登记/剖析/采纳/驳回/导出全部进 `audit_logs`。

## 4. 快速启动

```bash
cp .env.example .env
docker compose up -d --build
# 等 5/5 healthy
open http://localhost:18205
```

首次启动 backend 自动建表并执行一次 seed（`SEED_DEMO=true`）；seed 幂等，可重复执行：

```bash
docker compose exec -T backend python -m scripts.seed_demo
# SEED_SUMMARY brand=starmodel users=3 sources=24 runs=1 findings=9 pending=9
```

## 5. 本地开发

```bash
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
cd frontend/site && python -m http.server 5173   # 静态站，接口走 /api
```

## 6. 访问地址

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:18205 |
| 后端 API 文档 | http://localhost:19205/docs |
| 健康检查 | http://localhost:19205/api/health |
| 数据库映射 | localhost:17705 |

## 7. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | 原生 HTML5 + CSS（oklch 令牌 / 双字体）+ ES Modules；无框架、无打包 |
| 后端 | Python 3.11、FastAPI 0.115、SQLAlchemy 2.0、PyJWT、passlib(bcrypt) |
| 异步 | Celery 5.4 + Redis（worker 心跳 + 每日 07:40 全库重剖析） |
| 数据库 | MySQL 8.0 |
| 部署 | Docker Compose，恰好 5 服务 |

## 8. 目录

```text
backend/
  src/{config,constants,controllers,middlewares,models,routes,schemas,services,utils}
  scripts/{seed_demo.py,demo_config.py,worker_healthcheck.sh}
  migrations/  tests/
frontend/
  site/{index.html,css/{tokens,app}.css,js/{config,api,store,ui,app}.js,js/pages/*.js}
docker-compose.yml  .env  README.md
```

## 9. 核心算法与口径

### 算法 A｜候选键 + 包含依赖（`backend/src/services/profiling_service.py`）

- 输入：每张表的 200 行抽样（`source_tables.sample_rows`）。
- 逐列：`unique_ratio = 去重值数 / 抽样行数`（NULL 计入分母）、`null_ratio = 空值行 / 抽样行`、`cardinality = 去重值数`，保留 ≤64 个去重样本值。
- 候选键：`unique_ratio == 1` 且 `null_ratio == 0`。
- 外键候选：左列名以 `_id` 结尾、不是本表候选键；右列同名且是候选键；包含度 = 左侧去重样本值落在右侧样本集合的比例。
- 判定：包含度 ≥ 0.98 记外键候选；= 1.0 记 `pk-fk`（主外键），0.98 ≤ x < 1.0 记 `fk`（弱外键候选）。置信度 = `min(0.99, 0.60 + 0.33×包含度 + 0.06)`。
- 可复现：纯函数、无随机、无网络；同样样本两次结果完全一致。

### 算法 B｜星型建模建议（`backend/src/services/star_service.py`）

- 事实表：出边 ≥ 2 且存在度量列（amount/qty/points/cost/price…），并且表体量 ≥ 10 万行或度量列 ≥ 3（避免把带单价的商品维判成事实）。
- 维度表：存在候选键、≥2 个描述列（非 `*_id`、非度量、非日期）、体量 ≤ 10 万行；其余为无关表。
- 粒度：事实表的维度外键按源表列顺序组合（如 `store_id, sku_id, date_id` → 门店×商品×日期），对抽样行做去重计数。
- 建议范围：4 张事实 + 被事实直接引用的 5 张主维（共 9 条）；只被维表引用的 7 张为二级维（雪花），在 metrics 单列。
- DDL：事实表 = 代理键 + 维度外键 + 度量列 + `PRIMARY KEY` + 每条关系一条 `FOREIGN KEY`；维度表 = 代理键 + 属性列 + 上层维外键。
- 导出：`GET /api/exports/ddl.sql` 按「事实优先 + 目标表名」排序，固定 9 段，段头带序号/角色/置信度/状态。

### 关系图数据

`GET /api/relations/graph` 返回 24 个节点（含算法现算的 fact/dim/none 角色与度数）与 18 条边；角色只由 `classify_tables()` 计算，不落库、不由前端推断。

## 10. 共享枚举出现位置

| 枚举 | 后端 | 前端 |
|---|---|---|
| 角色 `admin/analyst/viewer` | `backend/src/constants/{roles,enums}.py` | `frontend/site/js/config.js`（`ENUMS.role` / `PERMISSIONS`） |
| 主题域 `sales/inventory/member/product/supply/org/log/config` | `backend/src/constants/enums.py`（`TableDomain`） | `frontend/site/js/config.js`（`ENUMS.domain`） |
| 字段类型 `int/decimal/date/string/bool` | `backend/src/constants/enums.py`（`DataType`） | `frontend/site/js/config.js`（`ENUMS.dtype`） |
| 关系类型 `pk-fk/fk` | `backend/src/constants/enums.py`（`RelationKind`） | `frontend/site/js/config.js`（`ENUMS.relationKind`） |
| 建议角色 `fact/dim` | `backend/src/constants/enums.py`（`SuggestionRole`） | `frontend/site/js/config.js`（`ENUMS.suggestionRole`） |
| 建议状态 `pending/adopted/dismissed` | `backend/src/constants/enums.py`（`SuggestionStatus`） | `frontend/site/js/config.js`（`ENUMS.suggestionStatus`） |
| 运行状态 `queued/running/success/partial/failed` | `backend/src/constants/enums.py`（`ModelRunStatus`） | `frontend/site/js/config.js`（`ENUMS.runStatus`） |

## 11. API

| 方法 | 路径 | 权限 |
|---|---|---|
| POST | `/api/auth/login` | 公开 |
| GET | `/api/overview` | 三角色 |
| GET | `/api/source-tables`、`/api/source-tables/{id}` | 三角色 |
| POST | `/api/source-tables` | admin |
| GET | `/api/profiles?table_id=` | 三角色 |
| GET | `/api/relations`、`/api/relations/graph` | 三角色 |
| GET / POST | `/api/model-runs` | 读：三角色；写：admin/analyst |
| GET | `/api/model-suggestions`、`/{id}` | 三角色 |
| POST | `/api/model-suggestions/{id}/adopt` | admin |
| POST | `/api/model-suggestions/{id}/dismiss` | admin/analyst |
| GET | `/api/exports/ddl.sql` | admin |
| GET | `/api/exports/relations.csv`、`/suggestions.csv` | admin/analyst |
| GET | `/api/audit` | admin |

## 12. Docker 说明

- 5 个服务：`frontend`(Nginx 静态站) / `backend`(uvicorn) / `worker`(Celery) / `db`(MySQL 8.0) / `redis`，全部带 healthcheck。
- 命名卷：`db_data`、`redis_data`；`/api` 由 Nginx 反代到 `backend:8000` 并剥掉前缀。
- 限流：Redis 固定窗口，读 300/min、写 60/min；审计中间件记录全部写请求。
- 收尾：`docker compose down -v --remove-orphans`。

## License

内部演示项目，仅用于评测与教学。
