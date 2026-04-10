#!/usr/bin/env python3
"""Seed the taxonomy_node table with a standard fashion label vocabulary.

Idempotent — skips nodes that already exist by (dimension, name).
Run from gallery-api/ directory:
    python scripts/seed_taxonomy.py
    python scripts/seed_taxonomy.py --dry-run   # print what would be inserted
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.assets.models import DimensionEnum, TaxonomyNode

# ── Category: 2-level tree ──────────────────────────────────────────────────
# Keys = top-level 品类 nodes; values = child nodes (品类细分).
# VLM outputs leaf names; parent nodes enable hierarchy browsing/filtering.
CATEGORY_TREE: dict[str, list[str]] = {
    "上衣": ["T恤", "衬衫", "飘带衬衫", "针织衫", "毛衣", "开衫", "背心", "卫衣"],
    "马甲": ["西装马甲", "针织马甲"],
    "外套": ["单件西装", "套装", "夹克"],
    "大衣": ["长大衣", "短大衣"],
    "风衣": ["经典风衣", "新中式风衣"],
    "羽绒服/棉服": ["羽绒服", "棉服"],
    "裤装": ["西装裤", "阔腿裤", "直筒裤", "休闲裤"],
    "半身裙": ["铅笔裙", "A字裙", "百褶裙", "鱼尾裙"],
    "连衣裙": ["西装式连衣裙", "礼服裙", "日常连衣裙", "针织连衣裙"],
}

# ── Style: flat list ────────────────────────────────────────────────────────
STYLE_NODES: list[str] = [
    # 品质/气质类
    "静奢", "知性", "干练", "职业", "精致", "华丽", "气场", "大气",
    # 文化/设计类
    "东方美学", "文化底蕴", "匠心", "设计感", "联名限定",
    # 风格倾向
    "优雅", "女性力量", "灵动", "百搭", "经典", "简约", "极简",
    # 情绪/质感
    "松弛感", "温润", "舒适", "休闲", "层次感",
]

# ── Scene: flat list ────────────────────────────────────────────────────────
SCENE_NODES: list[str] = [
    # 工作场景
    "职场通勤", "日常办公", "商务谈判", "正式会议", "重要场合",
    # 日常出行
    "日常出行", "日常通勤", "周末休闲", "差旅出行", "户外休闲",
    # 社交场景
    "商务社交", "约会聚会", "节庆聚会", "品牌活动",
    # 高端场合
    "晚宴", "社交酒会", "下午茶",
    # 文化场景
    "文化沙龙", "艺术展",
]


def _existing_names(db, dimension: DimensionEnum) -> set[str]:
    rows = db.query(TaxonomyNode.name).filter(TaxonomyNode.dimension == dimension).all()
    return {r.name for r in rows}


def seed(db, dry_run: bool = False) -> None:
    created = 0

    # ── category ──────────────────────────────────────────────────────────
    existing_cat = _existing_names(db, DimensionEnum.category)

    for sort_p, (parent_name, children) in enumerate(CATEGORY_TREE.items()):
        # top-level node
        if parent_name not in existing_cat:
            if not dry_run:
                parent_node = TaxonomyNode(
                    dimension=DimensionEnum.category,
                    name=parent_name,
                    sort_order=sort_p * 10,
                )
                db.add(parent_node)
                db.flush()
            else:
                print(f"  [category] + {parent_name}")
            created += 1
        else:
            parent_node = db.query(TaxonomyNode).filter(
                TaxonomyNode.dimension == DimensionEnum.category,
                TaxonomyNode.name == parent_name,
            ).first()

        # child nodes
        for sort_c, child_name in enumerate(children):
            if child_name not in existing_cat:
                if not dry_run:
                    db.add(TaxonomyNode(
                        dimension=DimensionEnum.category,
                        name=child_name,
                        parent_id=parent_node.id if not dry_run else None,
                        sort_order=sort_c,
                    ))
                else:
                    print(f"  [category]   └─ {child_name}")
                created += 1

    if not dry_run:
        db.flush()

    # ── style ─────────────────────────────────────────────────────────────
    existing_style = _existing_names(db, DimensionEnum.style)
    for i, name in enumerate(STYLE_NODES):
        if name not in existing_style:
            if not dry_run:
                db.add(TaxonomyNode(dimension=DimensionEnum.style, name=name, sort_order=i))
            else:
                print(f"  [style] + {name}")
            created += 1

    # ── scene ─────────────────────────────────────────────────────────────
    existing_scene = _existing_names(db, DimensionEnum.scene)
    for i, name in enumerate(SCENE_NODES):
        if name not in existing_scene:
            if not dry_run:
                db.add(TaxonomyNode(dimension=DimensionEnum.scene, name=name, sort_order=i))
            else:
                print(f"  [scene] + {name}")
            created += 1

    # color and detail are intentionally not pre-seeded:
    # VLM outputs free-form values; unknowns go to taxonomy_candidate for human review.

    if not dry_run:
        db.commit()

    print(f"{'[dry-run] Would create' if dry_run else 'Created'} {created} node(s).")


def main():
    parser = argparse.ArgumentParser(description="Seed taxonomy nodes")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        seed(db, dry_run=args.dry_run)
    finally:
        db.close()


if __name__ == "__main__":
    main()
