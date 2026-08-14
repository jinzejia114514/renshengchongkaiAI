# -*- coding: utf-8 -*-
"""
世界书标签系统 — 默认值、合并变化、清理、格式化显示
"""

import json

from game_data import WORLD_TAG_DEFAULTS


def get_world_tags(world):
    """获取世界的初始标签（从预设默认值中复制）"""
    wid = world.get('id', '')
    tags = WORLD_TAG_DEFAULTS.get(wid)
    if tags:
        return json.loads(json.dumps(tags))
    parent = world.get('parent')
    if parent and parent in WORLD_TAG_DEFAULTS:
        return json.loads(json.dumps(WORLD_TAG_DEFAULTS[parent]))
    return {}


def _merge_world_tag_changes(game_tags, changes):
    """将 LLM 返回的世界书变化量（加减值）累加到 game_tags。
    支持三种格式：
      1. 点号扁平格式: {'社会结构.社会阶层': 2}
      2. 嵌套格式:     {'社会结构': {'社会阶层': 2}}
      3. 简单标量格式: {'新分类名': 5}
    删除语义：值为 null → 删除标签/分类。
    """
    for key, val in changes.items():
        # 删除语义：点号格式中值为 null → 删除该标签
        if '.' in key and val is None:
            cat, tag = key.split('.', 1)
            if cat in game_tags and isinstance(game_tags[cat], dict):
                game_tags[cat].pop(tag, None)
                if not game_tags[cat]:
                    game_tags.pop(cat, None)
            continue
        # 删除语义：整个分类设为 null → 直接移除分类
        if val is None:
            game_tags.pop(key, None)
            continue
        if isinstance(val, dict):
            cat = key
            if cat not in game_tags:
                game_tags[cat] = {}
            if not isinstance(game_tags[cat], dict):
                continue
            for tag, v in val.items():
                if v is None:
                    game_tags[cat].pop(tag, None)
                    continue
                try:
                    delta = int(v)
                    old = game_tags[cat].get(tag, 0)
                    if isinstance(old, (int, float)):
                        game_tags[cat][tag] = old + delta
                    else:
                        game_tags[cat][tag] = delta
                except (ValueError, TypeError):
                    pass
            if not game_tags[cat]:
                game_tags.pop(cat, None)
        elif '.' in key and isinstance(val, (int, float, str)):
            cat, tag = key.split('.', 1)
            if cat not in game_tags:
                game_tags[cat] = {}
            if not isinstance(game_tags[cat], dict):
                continue
            try:
                delta = int(val)
                old = game_tags[cat].get(tag, 0)
                if isinstance(old, (int, float)):
                    game_tags[cat][tag] = old + delta
                else:
                    game_tags[cat][tag] = delta
            except (ValueError, TypeError):
                pass
            if not game_tags.get(cat):
                game_tags.pop(cat, None)
        elif isinstance(val, (int, float)):
            cat = key
            if cat not in game_tags:
                game_tags[cat] = {}
            if not isinstance(game_tags[cat], dict):
                continue
            try:
                delta = int(val)
                old = game_tags[cat].get('总值', 0)
                if isinstance(old, (int, float)):
                    game_tags[cat]['总值'] = old + delta
                else:
                    game_tags[cat]['总值'] = delta
            except (ValueError, TypeError):
                pass


def _clean_world_tags(tags):
    """递归清理世界书标签：移除值为 None 的标签和空的分类。"""
    if not isinstance(tags, dict):
        return tags
    cleaned = {}
    for k, v in tags.items():
        if isinstance(v, dict):
            inner = {sk: sv for sk, sv in v.items() if sv is not None}
            if inner:
                cleaned[k] = inner
        elif v is not None:
            cleaned[k] = v
    return cleaned


def format_world_tags(tags):
    """格式化世界书标签，支持预定义分类和新添加的分类"""
    if not tags:
        return ''
    predefined_labels = {
        '社会结构': '【社会结构】', '自然环境': '【自然环境】',
        '经济体系': '【经济体系】', '超自然': '【超自然】',
        '人口构成': '【人口构成】', '文化面貌': '【文化面貌】',
    }
    lines = ['\n=== 世界书 ===']
    for key, label in predefined_labels.items():
        cat = tags.get(key, {})
        if cat and isinstance(cat, dict):
            parts = [f'{k}: {v}' for k, v in cat.items()]
            lines.append(f'{label}  {" | ".join(parts)}')
    for key, cat in tags.items():
        if key in predefined_labels:
            continue
        if cat and isinstance(cat, dict):
            label = f'【{key}】'
            parts = [f'{k}: {v}' for k, v in cat.items()]
            lines.append(f'{label}  {" | ".join(parts)}')
    return '\n'.join(lines)
