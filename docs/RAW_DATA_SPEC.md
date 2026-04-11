# 原始数据存放规范（Raw Data Spec）

## 1. 目标

统一原始图片目录与命名，保证系统可自动识别：
- 资产类型（广告图 / 平铺图 / 模特组图）
- 商品编码（单品 / 多商品）
- 可追溯来源

## 2. 顶层目录

建议固定为三类：

1. `flatlay/`：单品平铺图
2. `advertising/`：广告图/套装图
3. `model_set/`：模特组图/搭配图

## 3. 命名规则

### 3.1 flatlay

- 文件命名：`<product_code>[_suffix].jpg`
- 示例：
  - `flatlay/B120330.jpg`
  - `flatlay/15111022A.jpg`

### 3.2 advertising

- 目录命名：`<product_code>&<product_code>[&...]`
- 目录内文件可用序号命名
- 示例：
  - `advertising/B120295&B103385/001.jpg`
  - `advertising/B113422&B103125&B142169/012.jpg`

### 3.3 model_set

- 推荐目录命名为主商品编码
- 文件可用序号命名
- 示例：
  - `model_set/A712759/001.jpg`
  - `model_set/A712759/002.jpg`

## 4. 不可解析数据

若暂时无法确认商品编码，使用：
- 目录或文件前缀：`UNRESOLVED_`
- 示例：
  - `advertising/UNRESOLVED_batch1_001/001.jpg`

系统将其标记为 `parse_status=unresolved`，后续人工绑定商品。

## 5. 推荐 manifest（强烈建议）

每批数据附带 `manifest.csv`，字段建议：

1. `source_relpath`
2. `asset_type` (`flatlay|advertising|model_set`)
3. `product_codes`（多商品用 `;` 分隔）
4. `season`
5. `category`
6. `shot_group`
7. `note`

这样可避免仅依赖目录猜测，导入准确率更高。
