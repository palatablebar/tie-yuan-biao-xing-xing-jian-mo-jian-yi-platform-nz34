"""禾丰零售贴源表样本（24 张：4 事实候选 / 12 维 / 8 无主键流水）。

全部字段与样本行由本文件的纯函数生成，同一进程多次调用结果一致；
seed 只负责 upsert，算法在运行时从样本行重新剖析，前端不参与任何计算。
"""
from __future__ import annotations

DEMO_PASSWORD = "Demo@2026"

DEMO_USERS = [
    ("admin@starmodel.io", "林可 · 平台管理员", "admin"),
    ("analyst@starmodel.io", "周棠 · 建模专员", "analyst"),
    ("viewer@starmodel.io", "陈默 · 只读访客", "viewer"),
]

ORG = "禾丰零售 · 数仓组"

REGION_NAMES = ["华东大区", "华南大区", "华北大区", "西南大区", "东北大区"]
CITIES = [
    "上海", "杭州", "广州", "深圳", "北京", "天津", "成都", "重庆",
    "沈阳", "大连", "南京", "苏州", "武汉", "长沙", "青岛", "济南",
    "西安", "郑州", "合肥", "福州", "厦门", "昆明", "贵阳", "宁波",
]
LEVEL_NAMES = ["普通会员", "银卡会员", "金卡会员", "铂金会员", "黑金会员"]
CATEGORY_NAMES = ["粮油", "生鲜", "乳品", "休闲零食", "酒饮", "日化", "家居", "母婴"]
BRAND_NAMES = ["禾丰优选", "北纬四十五", "晨光牧场", "山海渔场", "谷雨工坊", "南岭果园", "清风日用", "小满母婴", "长白山泉", "金穗粮油", "云岭茶业", "海盐工社"]
CHANNEL_NAMES = ["线下门店", "微信小程序", "美团闪购", "京东到家", "抖音商城"]
SUPPLIER_NAMES = ["沈阳粮贸", "广州鲜配", "北京乳源", "成都日化", "青岛冷链", "杭州果业", "上海酒类", "郑州面业", "昆明茶叶", "宁波水产", "济南家居", "合肥母婴"]
ROLE_NAMES = ["店长", "副店长", "收银员", "理货员", "生鲜主管"]


def _regions() -> list[dict]:
    return [
        {
            "region_id": index,
            "region_name": name,
            "manager": f"王兼{index}",
            "province": f"{CITIES[index - 1]}等{2 + index}省",
            "city_count": 2 + index,
            "area_km2": 12000 + index * 860,
            "status": "启用",
        }
        for index, name in enumerate(REGION_NAMES, start=1)
    ]


def _stores() -> list[dict]:
    rows = []
    for index, city in enumerate(CITIES):
        store_id = 1001 + index
        rows.append(
            {
                "store_id": store_id,
                "store_name": f"禾丰{city}示范店",
                "region_id": 1 + index % 5,
                "city": city,
                "address": f"{city}市示范路{index + 1}号",
                "phone": f"021-6{index:03d}8821",
                "manager": f"店长{index + 1:02d}",
                "open_date": f"20{15 + index % 8}-0{1 + index % 9}-15",
                "area_sqm": 180 + (index % 10) * 26,
                "lat": round(31.2 + index * 0.11, 4),
                "lng": round(121.4 + index * 0.13, 4),
                "status": "营业中",
            }
        )
    return rows


def _skus() -> list[dict]:
    rows = []
    for index in range(40):
        sku_id = f"SKU-{index + 1:04d}"
        rows.append(
            {
                "sku_id": sku_id,
                "sku_name": f"禾丰商品{index + 1:03d}",
                "category_id": 1 + index % 8,
                "brand_id": 1 + index % 12,
                "price": round(9.9 + index * 3.7, 2),
                "unit": "件" if index % 2 == 0 else "箱",
                "weight_g": 250 + index * 37,
                "color": "原色",
                "size": "标准",
                "barcode": f"69{index:010d}",
                "shelf_life_days": 30 + index % 12 * 30,
                "status": "在售",
            }
        )
    return rows


def _dates() -> list[dict]:
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    rows = []
    for index in range(30):
        day = index + 1
        rows.append(
            {
                "date_id": 20240500 + day,
                "date": f"2024-05-{day:02d}",
                "year": 2024,
                "month": 5,
                "quarter": 2,
                "weekday": weekdays[index % 7],
                "is_weekend": index % 7 >= 5,
                "is_holiday": day == 1,
            }
        )
    return rows


def _members() -> list[dict]:
    rows = []
    for index in range(60):
        rows.append(
            {
                "member_id": f"M-{index + 1:04d}",
                "member_name": f"会员{index + 1:03d}",
                "level_id": 1 + index % 5,
                "join_date": f"20{18 + index % 6}-{1 + index % 12:02d}-08",
                "phone": f"138{index:04d}6621",
                "gender": "女" if index % 2 == 0 else "男",
                "birthday": f"19{70 + index % 30}-{1 + index % 12:02d}-12",
                "city": CITIES[index % len(CITIES)],
                "points_total": 200 + index * 37,
                "status": "正常",
            }
        )
    return rows


def _levels() -> list[dict]:
    return [
        {
            "level_id": index,
            "level_name": name,
            "discount": round(1 - index * 0.03, 2),
            "min_points": index * 500,
            "benefits": f"积分{index}倍",
            "note": "按年度消费额升降级",
        }
        for index, name in enumerate(LEVEL_NAMES, start=1)
    ]


def _suppliers() -> list[dict]:
    return [
        {
            "supplier_id": f"SUP-{index + 1:02d}",
            "supplier_name": name,
            "region_id": 1 + index % 5,
            "contact": f"联络人{index + 1:02d}",
            "phone": f"010-8{index:03d}2201",
            "tax_no": f"91310000MA{index:07d}",
            "bank_account": f"6222 0212 00{index:04d} 8891",
            "pay_terms": "月结30天",
            "status": "合作中",
        }
        for index, name in enumerate(SUPPLIER_NAMES)
    ]


def _categories() -> list[dict]:
    return [
        {
            "category_id": index,
            "category_name": name,
            "parent_name": "食品" if index <= 5 else "非食品",
            "level": 1,
            "sort_no": index * 10,
            "description": f"{name}大类目",
            "status": "启用",
        }
        for index, name in enumerate(CATEGORY_NAMES, start=1)
    ]


def _brands() -> list[dict]:
    return [
        {
            "brand_id": index,
            "brand_name": name,
            "country": "中国" if index % 4 else "新西兰",
            "founded_year": 1985 + index,
            "owner": f"品牌方{index:02d}",
            "logo_text": name[:2],
            "status": "合作中",
        }
        for index, name in enumerate(BRAND_NAMES, start=1)
    ]


def _channels() -> list[dict]:
    return [
        {
            "channel_id": index,
            "channel_name": name,
            "type": "自营" if index <= 2 else "平台",
            "enabled": True,
            "fee_rate": round(0.01 + index * 0.004, 3),
            "note": "线上订单按渠道结算",
        }
        for index, name in enumerate(CHANNEL_NAMES, start=1)
    ]


def _promotions() -> list[dict]:
    return [
        {
            "promo_id": f"P-{index + 1:02d}",
            "promo_name": f"2024年5月第{index + 1}档促销",
            "channel_id": 1 + index % 5,
            "start_date": f"2024-05-{index + 1:02d}",
            "end_date": f"2024-05-{index + 10:02d}",
            "discount": round(0.95 - index * 0.02, 2),
            "budget_amt": 20000 + index * 3500,
            "status": "进行中" if index < 6 else "未开始",
        }
        for index in range(10)
    ]


def _employees() -> list[dict]:
    return [
        {
            "employee_id": f"E-{index + 1:03d}",
            "emp_name": f"员工{index + 1:03d}",
            "store_id": 1001 + index % 10,
            "role_name": ROLE_NAMES[index % len(ROLE_NAMES)],
            "hire_date": f"20{20 + index % 4}-0{1 + index % 9}-10",
            "phone": f"139{index:04d}5512",
            "email": f"emp{index + 1:03d}@hefeng-retail.cn",
            "status": "在职",
        }
        for index in range(20)
    ]


def _sales_rows() -> list[dict]:
    stores, skus, dates = _stores(), _skus(), _dates()
    rows = []
    for index in range(200):
        store = stores[index % 24]
        sku = skus[(index * 7) % 40]
        day = dates[(index * 13) % 30]
        qty = 1 + index % 5
        unit_price = sku["price"]
        amount = round(qty * unit_price * (1 - (index % 7) * 0.01), 2)
        rows.append(
            {
                "order_item_id": f"SOI-{index + 1:05d}",
                "order_no": f"SO-202405-{index // 3 + 1:04d}",
                "store_id": store["store_id"],
                "sku_id": sku["sku_id"],
                "date_id": day["date_id"],
                "qty": qty,
                "unit_price": unit_price,
                "amount": amount,
                "discount_amt": round(amount * 0.02, 2),
                "tax_amt": round(amount * 0.09, 2),
                "channel_code": f"CH{1 + index % 5}",
                "promo_code": f"P-{1 + index % 10:02d}",
                "source_batch": "batch-202405-daily",
                "created_at": f"2024-05-{day['date'][-2:]} 10:{index % 60:02d}:00",
            }
        )
    return rows


def _inventory_rows() -> list[dict]:
    stores, skus, dates = _stores(), _skus(), _dates()
    rows = []
    for index in range(200):
        store = stores[index % 24]
        sku = skus[(index * 11) % 40]
        day = dates[(index * 7) % 30]
        on_hand = 40 + (index * 3) % 260
        rows.append(
            {
                "snapshot_id": f"INV-{index + 1:05d}",
                "store_id": store["store_id"],
                "sku_id": sku["sku_id"],
                "date_id": day["date_id"],
                "on_hand_qty": on_hand,
                "cost_amt": round(on_hand * sku["price"] * 0.62, 2),
                "batch_no": f"B{20240500 + index % 30}",
                "expire_date": f"2024-{6 + index % 4:02d}-15",
                "warehouse_code": f"WH{1 + index % 6:02d}",
                "updated_at": f"2024-05-{day['date'][-2:]} 23:{index % 60:02d}:00",
            }
        )
    return rows


def _purchase_rows() -> list[dict]:
    suppliers, stores, dates = _suppliers(), _stores(), _dates()
    rows = []
    for index in range(120):
        supplier = suppliers[(index * 5) % 12]
        store = stores[(index * 7) % 24]
        day = dates[(index * 11) % 30]
        qty = 20 + (index * 7) % 180
        rows.append(
            {
                "po_id": f"PO-{index + 1:05d}",
                "po_no": f"PO-2024-{index // 4 + 1:05d}",
                "supplier_id": supplier["supplier_id"],
                "store_id": store["store_id"],
                "date_id": day["date_id"],
                "qty": qty,
                "amount": round(qty * (8 + index % 40) * 0.9, 2),
                "receive_date": f"2024-05-{day['date'][-2:]}",
                "buyer": f"采购{1 + index % 6:02d}",
                "status": "已入库" if index % 5 else "运输中",
                "updated_at": f"2024-05-{day['date'][-2:]} 18:{index % 60:02d}:00",
            }
        )
    return rows


def _points_rows() -> list[dict]:
    members, dates = _members(), _dates()
    rows = []
    for index in range(200):
        member_id = members[(index * 9) % 59]["member_id"] if index % 25 != 0 else "M-0099"
        day = dates[(index * 3) % 30]
        rows.append(
            {
                "points_id": f"PT-{index + 1:05d}",
                "member_id": member_id,
                "date_id": day["date_id"],
                "points": 5 + (index * 3) % 80,
                "amount": round(20 + (index % 40) * 3.5, 2),
                "balance": 500 + index * 7,
                "biz_type": "消费赠送" if index % 3 else "积分兑换",
                "rule_code": f"R{1 + index % 4:02d}",
                "note": "按月结算",
                "created_at": f"2024-05-{day['date'][-2:]} 12:{index % 60:02d}:00",
            }
        )
    return rows


def _duplicated(rows: list[dict]) -> list[dict]:
    """无主键流水：20 行原始 + 复制一份 → 抽样中每列都有重复值，无候选键。"""
    return [dict(row) for row in rows] + [dict(row) for row in rows]


def _log_rows() -> list[dict]:
    levels = ["INFO", "WARN", "ERROR", "DEBUG", "INFO"]
    base = [
        {
            "log_seq": 1 + index % 20,
            "level": levels[index % 5],
            "message": f"etl job step failed: partition {index % 7}",
            "created_at": f"2024-05-1{index % 9} 0{index % 10}:15:00",
            "source": "ods-loader",
        }
        for index in range(20)
    ]
    return _duplicated(base)


def _trail_rows() -> list[dict]:
    actions = ["INSERT", "UPDATE", "DELETE", "TRUNCATE", "MERGE"]
    base = [
        {
            "trail_seq": 1 + index % 20,
            "action": actions[index % 5],
            "actor": f"etl_{index % 4}",
            "ts": f"2024-05-1{index % 9} 0{index % 10}:20:00",
            "ip": f"10.0.{index % 8}.{index % 200}",
        }
        for index in range(20)
    ]
    return _duplicated(base)


def _config_rows() -> list[dict]:
    base = [
        {
            "config_key": f"etl.{name}.batch_size",
            "config_value": str(500 + index * 100),
            "updated_at": f"2024-05-0{1 + index % 9} 09:00:00",
            "owner": f"数仓{index % 5}组",
        }
        for index, name in enumerate(
            ["sales", "inventory", "purchase", "member", "promo", "price", "stock", "store", "sku", "channel",
             "region", "category", "brand", "supplier", "employee", "level", "delivery", "return", "settle", "audit"]
        )
    ]
    return _duplicated(base)


def _watermark_rows() -> list[dict]:
    jobs = ["ods_sales", "ods_inventory", "ods_purchase", "ods_member", "ods_promo"]
    base = [
        {
            "job_name": jobs[index % 5],
            "last_ts": f"2024-05-{1 + index:02d} 0{index % 10}:00:00",
            "rows": 120000 + index * 4300,
            "status": "ok" if index % 4 else "retry",
        }
        for index in range(20)
    ]
    return _duplicated(base)


def _upload_rows() -> list[dict]:
    base = [
        {
            "file_name": f"price_202405{1 + index % 20:02d}.csv",
            "size": 10240 + index * 512,
            "ts": f"2024-05-{1 + index:02d} 08:30:00",
            "operator": f"op{index % 6:02d}",
            "store_id": 9001 + index % 10,
        }
        for index in range(20)
    ]
    return _duplicated(base)


def _dict_rows() -> list[dict]:
    codes = ["pay_type", "order_status", "return_reason", "member_source", "channel_type"]
    base = [
        {
            "dict_code": codes[index % 5],
            "dict_label": f"字典项{index + 1:02d}",
            "sort_no": index + 1,
            "enabled": index % 3 != 0,
        }
        for index in range(20)
    ]
    return _duplicated(base)


def _cache_rows() -> list[dict]:
    base = [
        {
            "cache_key": f"sku:price:{1000 + index}",
            "hit": 120 + index * 3,
            "miss": 8 + index % 5,
            "ts": f"2024-05-1{index % 9} 1{index % 10}:00:00",
        }
        for index in range(20)
    ]
    return _duplicated(base)


def _notice_rows() -> list[dict]:
    base = [
        {
            "title": f"数据同步通知第{index + 1}期",
            "content": "本月贴源表结构冻结，新增字段需走变更单。",
            "published_at": f"2024-05-{1 + index:02d} 10:00:00",
            "author": f"数仓{index % 5}组",
        }
        for index in range(20)
    ]
    return _duplicated(base)


def _table(name, cn_name, subject, domain, row_count, note, rows) -> dict:
    return {
        "name": name,
        "cn_name": cn_name,
        "subject": subject,
        "domain": domain,
        "row_count": row_count,
        "note": note,
        "sample_rows": rows,
    }


TABLES: list[dict] = [
    _table("ods_sales_order_item", "销售订单明细", "sales", "sales", 8_640_000,
           "门店 POS + 小程序订单合并明细，一行一个订单行", _sales_rows()),
    _table("ods_inventory_snapshot", "库存快照", "inventory", "inventory", 12_800_000,
           "每日闭店后按门店×商品×日期全量快照", _inventory_rows()),
    _table("ods_purchase_order", "采购订单", "purchase", "supply", 960_000,
           "总部向供应商下单明细，含收货标记", _purchase_rows()),
    _table("ods_member_points", "会员积分流水", "member_points", "member", 5_200_000,
           "积分获取与消耗流水，存在少量历史脏会员号", _points_rows()),
    _table("ods_store", "门店", "store", "org", 312,
           "300 家门店 + 12 家已闭店历史门店", _stores()),
    _table("ods_sku", "商品", "sku", "product", 1_860,
           "在售 SKU，价格与条码来自商品主档", _skus()),
    _table("ods_date", "日期", "date", "org", 1_095,
           "三年日期维，含节假日标记", _dates()),
    _table("ods_member", "会员", "member", "member", 486_000,
           "全量会员主档，含等级与注册渠道", _members()),
    _table("ods_member_level", "会员等级", "member_level", "member", 5,
           "等级规则表，年度调整一次", _levels()),
    _table("ods_supplier", "供应商", "supplier", "supply", 46,
           "签约供应商主档", _suppliers()),
    _table("ods_region", "区域", "region", "org", 5,
           "大区划分，与门店/供应商的归属关系", _regions()),
    _table("ods_category", "品类", "category", "product", 32,
           "三级品类压缩为一级大类的映射", _categories()),
    _table("ods_brand", "品牌", "brand", "product", 118,
           "品牌主档，含国别与成立年份", _brands()),
    _table("ods_channel", "渠道", "channel", "sales", 6,
           "自营与平台渠道，含费率", _channels()),
    _table("ods_promotion", "促销活动", "promotion", "sales", 210,
           "月度促销档期与预算", _promotions()),
    _table("ods_employee", "员工", "employee", "org", 1_240,
           "门店员工主档，含岗位与入职日期", _employees()),
    _table("ods_error_log", "ETL 错误日志", "error_log", "log", 2_400_000,
           "装载失败日志，无唯一键，按分区追加", _log_rows()),
    _table("ods_audit_trail", "库表变更审计", "audit_trail", "log", 9_800_000,
           "业务库触发器写入的变更流水，无唯一键", _trail_rows()),
    _table("ods_sys_config", "ETL 参数配置", "sys_config", "config", 240,
           "批次大小等运行参数，历史版本共存", _config_rows()),
    _table("ods_etl_watermark", "装载水位", "etl_watermark", "config", 36,
           "每个作业每次运行的完成水位", _watermark_rows()),
    _table("ods_temp_upload", "临时上传表", "temp_upload", "log", 1_200,
           "门店手工上传的价格文件记录，file_name 不唯一", _upload_rows()),
    _table("ods_dict_item", "字典项", "dict_item", "config", 480,
           "业务字典，一个 code 多条 label", _dict_rows()),
    _table("ods_cache_stat", "缓存命中统计", "cache_stat", "log", 3_600_000,
           "分钟级缓存命中流水，无唯一键", _cache_rows()),
    _table("ods_notice", "数仓通知", "notice", "config", 86,
           "面向业务方的结构变更通知", _notice_rows()),
]

SEED_RUNS = [("seed-run-a", "seed", "admin@starmodel.io")]
