# Changelog

## release1.1 - 2026-04-18

### Added
- 新增销售数据表与迁移：
  - `sales_order_raw`
  - `product_sales_summary`
- 新增销售同步能力：
  - `POST /products/admin/sales/sync`
  - `scripts/sync_sales_from_budan.py`
- 新增 `BUDAN_DATABASE_URL` 配置项。
- 商品与商品检索返回中新增 `sales_total_qty` 字段。
- 商品列表与商品维度检索新增销量筛选参数：
  - `sales_min`
  - `sales_max`

### Changed
- API 应用版本升级到 `1.1.0`。
- 商品列表排序逻辑中继续保留 `TMPUID-*` 置后策略，并支持按销量排序。

### Verification
- 测试通过：`98 passed`（`pytest -q`，2026-04-18 本地执行）。

## release1.0 - 2026-04-12

### Baseline
- 运营端定版能力：资产管理、标签体系、商品管理、向量检索、Lookbook、任务查询。
