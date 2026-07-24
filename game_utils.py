# -*- coding: utf-8 -*-
"""
游戏工具函数 — 天赋抽取、属性应用、年龄图标、世界查找、存档保存、内容审核
"""

import json
import random
import time
from datetime import datetime
from pathlib import Path

from flask import session

from game_data import TALENTS, WORLDS


def draw_talents(count=3):
    """抽取天赋"""
    common = [t for t in TALENTS if t['rarity'] == 'common']
    rare = [t for t in TALENTS if t['rarity'] == 'rare']
    epic = [t for t in TALENTS if t['rarity'] == 'epic']
    legendary = [t for t in TALENTS if t['rarity'] == 'legendary']

    selected = []
    for _ in range(count):
        r = random.random()
        if r < 0.02:
            pool = legendary
        elif r < 0.15:
            pool = epic
        elif r < 0.45:
            pool = rare
        else:
            pool = common
        available = [t for t in pool if t not in selected]
        if available:
            selected.append(random.choice(available))
    return selected


def apply_talents_to_traits(traits, talents):
    """应用天赋效果到属性"""
    for talent in talents:
        for trait, value in talent.get('effect', {}).items():
            if trait in traits:
                traits[trait] = max(0, min(10, traits[trait] + value))
    return traits


def check_entry():
    """检查是否从首页进入，防止直接访问游戏页面"""
    return bool(session.get('entry_origin'))


def get_age_icon(age):
    """根据年龄返回对应的 emoji"""
    if age < 3:
        return '👶'
    elif age < 12:
        return '👧' if age % 2 == 0 else '👦'
    elif age < 18:
        return '🧑'
    elif age < 30:
        return '👱'
    elif age < 50:
        return '👨'
    else:
        return '👴'


def get_world(world_id):
    """获取世界数据（支持自定义世界）"""
    world = next((w for w in WORLDS if w['id'] == world_id), None)
    if not world and world_id in ('custom', 'random'):
        game = session.get('game', {})
        world = game.get('custom_world') if game else None
        if not world:
            world = session.get('custom_world')
        if world:
            world['unlocked'] = True
            if game.get('world_name') and world_id == 'random':
                world['name'] = game['world_name']
    return world


def moderate_content_text(text, llm_client, override=None):
    """调用 LLM 审核文本内容是否违规。返回 (is_clean, reason)。"""
    if not llm_client._is_llm_usable(override):
        return True, ''  # LLM 不可用时跳过审核，允许保存
    try:
        messages = [
            {
                'role': 'system',
                'content': (
                    '你是一个内容审核员。判断文本是否包含：\n'
                    '1. 色情内容\n2. 恐怖/暴力内容\n3. 涉及中国现代政治的敏感内容\n\n'
                    '严格仅以JSON回复：{"violation": true/false, "reason": "原因"}'
                )
            },
            {'role': 'user', 'content': f'请审核以下内容：\n\n{text}'}
        ]
        resp = llm_client._make_request(messages, override)
        if resp.status_code != 200:
            return False, f'LLM 审核请求失败 (HTTP {resp.status_code})'

        result = resp.json()
        content = result['choices'][0]['message']['content'].strip()
        # 复用 LLMClient 的 JSON 解析逻辑
        moderation = llm_client._parse_json_response(content)
        if moderation and isinstance(moderation, dict):
            if moderation.get('violation'):
                return False, moderation.get('reason', '内容违规')
            return True, ''
        # 解析失败时回退到简单关键词检测
        lower = content.lower()
        if '"violation": true' in lower or '"violation":true' in lower:
            return False, '内容违规（LLM判定）'
        return False, 'LLM 审核结果解析失败'
    except Exception as e:
        print(f'[Moderation] 审核异常: {e}')
        return False, f'审核过程异常: {e}'


# 记录缓存（模块级共享）
_records_cache = {'data': None, 'mtime': 0}


def get_records_list(records_dir):
    """获取所有公开记录列表（带缓存）"""
    dir_mtime = records_dir.stat().st_mtime if records_dir.exists() else 0
    if _records_cache['data'] is not None and _records_cache['mtime'] == dir_mtime:
        return _records_cache['data']

    result = []
    for f in sorted(records_dir.glob('*.json'), reverse=True):
        if 'nodisplay' in f.name:
            continue
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            result.append({
                'filename': f.name,
                'world': data.get('world', '未知'),
                'player_name': data.get('player_name', ''),
                'lifespan': data.get('lifespan', 0),
                'score': data.get('ending', {}).get('score', 0),
                'saved_at': data.get('saved_at', ''),
                'title': data.get('ending', {}).get('title', ''),
            })
        except:
            pass
    _records_cache['data'] = result
    _records_cache['mtime'] = dir_mtime
    return result


def save_game_record(world, game, ending, llm_client, override=None):
    """保存游玩记录到 records 文件夹。如果内容审核不通过则不保存。"""
    # 内容审核
    moderation_text_parts = []
    for h in game.get('history', []):
        moderation_text_parts.append(h.get('event', ''))
        if h.get('choice'):
            moderation_text_parts.append(h['choice'])
    if ending:
        moderation_text_parts.append(ending.get('title', ''))
        moderation_text_parts.append(ending.get('text', ''))
        moderation_text_parts.append(ending.get('summary', ''))
    moderation_text = '\n'.join(p for p in moderation_text_parts if p)

    is_clean, violation_reason = moderate_content_text(moderation_text, llm_client, override)
    if not is_clean:
        print(f'[Record] 保存被拒绝，内容违规: {violation_reason}')
        return False, violation_reason

    try:
        records_dir = Path(__file__).parent / 'records'
        records_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        world_name = world.get('name', 'unknown') if world else 'unknown'
        if not world_name or world_name == 'unknown':
            world_name = game.get('world_name', '随机世界')
        player_name = game.get('player_name', '').strip()
        show_record = game.get('show_record', True)

        name_part = f'_{player_name}' if player_name else ''
        display_part = '' if show_record else '_nodisplay'
        filename = f'{timestamp}_{world_name}{name_part}{display_part}.json'

        history_list = game.get('history', [])
        lifespan = max(h['year'] for h in history_list) - min(h['year'] for h in history_list) if history_list else 0

        record = {
            'saved_at': datetime.now().isoformat(),
            'world': world_name,
            'player_name': player_name,
            'gender': game.get('gender', {}).get('name', '未知'),
            'race': game.get('race', {}).get('name', '未知'),
            'custom_race': game.get('custom_race', ''),
            'custom_race_desc': game.get('custom_race_desc', ''),
            'destiny': game.get('custom_destiny', ''),
            'talents': [t['name'] for t in game.get('talents', [])],
            'traits': game.get('traits', {}),
            'background': game.get('background', ''),
            'world_tags': game.get('world_tags', {}),
            'relationships': game.get('relationships', []),
            'inventory': game.get('inventory', []),
            'conditions': game.get('conditions', []),
            'journal': game.get('journal', []),
            'time_unit': world.get('time_unit', '岁') if world else '岁',
            'ending_type': world.get('ending_type', '') if world else '',
            'history': [
                {
                    'year': h['year'], 'event': h['event'],
                    'choice': h.get('choice', ''),
                    'trait_changes': h.get('trait_changes', {}),
                    'world_tag_changes': h.get('world_tag_changes', {}),
                    'age_icon': h.get('age_icon', '')
                }
                for h in history_list
            ],
            'ending': {
                'title': ending.get('title', ''),
                'text': ending.get('text', ''),
                'type': ending.get('type', 'normal'),
                'score': ending.get('score', 0),
                'summary': ending.get('summary', ''),
            },
            'lifespan': lifespan,
            'show_record': show_record,
            'generated_image': game.get('generated_image', ''),
        }

        filepath = records_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        _records_cache['data'] = None
        _records_cache['mtime'] = 0
        print(f'[Record] 已保存: {filepath}')
        return True, ''
    except Exception as e:
        print(f'[Record] 保存失败: {e}')
        return False, str(e)


def cleanup_old_sessions(session_dir):
    """清理超过24小时的旧session文件"""
    try:
        now = time.time()
        cutoff = 24 * 3600
        for f in session_dir.glob('*'):
            if f.is_file() and (now - f.stat().st_mtime) > cutoff:
                try:
                    f.unlink()
                    print(f'[Session] 已清理: {f.name}')
                except:
                    pass
    except Exception as e:
        print(f'[Session] 清理异常: {e}')
