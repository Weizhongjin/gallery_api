# unresolved 资产占位 UID 规范与执行记录

## 背景

部分资产无法从文件名/目录自动解析商品编码（`parse_status=unresolved`）。  
为保证这些资产先进入统一商品体系，采用占位商品编码策略。

## 占位编码规则

编码前缀固定：

- `TMPUID-`

编码格式：

- `TMPUID-<12位资产ID片段>`
- 示例：`TMPUID-1E0CBE5674E5`

对应绑定写入：

1. `product.product_code = TMPUID-*`
2. `asset_product.source = placeholder_uid`
3. `asset_product.relation_role = manual`
4. `asset.parse_status` 仍保持 `unresolved`（用于后续人工处理队列）

## 本次执行记录（2026-04-11）

执行结果：

1. unresolved 资产总数：`126`
2. 新增占位商品：`126`
3. 新增占位绑定：`126`

执行后统计：

1. `unresolved_assets = 126`
2. `placeholder_products = 126`
3. `placeholder_links = 126`

## 后续人工替换流程

1. 在商品管理端新建/确认正式 `product_code`
2. 将资产从 `TMPUID-*` 改绑到正式商品
3. 移除对应 `TMPUID-*` 绑定
4. 若该占位商品无资产关联，可删除占位商品
5. 完成后可将对应资产 `parse_status` 改为 `parsed`（建议由工具或批处理统一执行）

## 推荐 SQL（核对）

```sql
-- 占位商品数量
SELECT COUNT(*) FROM product WHERE product_code LIKE 'TMPUID-%';

-- 占位绑定数量
SELECT COUNT(*)
FROM asset_product ap
JOIN product p ON p.id = ap.product_id
WHERE p.product_code LIKE 'TMPUID-%';

-- unresolved 且仍绑定占位商品的资产
SELECT a.id, a.filename, a.source_relpath, p.product_code
FROM asset a
JOIN asset_product ap ON ap.asset_id = a.id
JOIN product p ON p.id = ap.product_id
WHERE a.parse_status = 'unresolved'
  AND p.product_code LIKE 'TMPUID-%'
ORDER BY a.created_at DESC;
```
