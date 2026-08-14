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
from paths import RECORDS_DIR


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


def save_game_record(world, game, ending, llm_client=None, override=None):
    """保存游玩记录到 records 文件夹。不做内容审核，直接保存。"""
    try:
        records_dir = RECORDS_DIR
        records_dir.mkdir(parents=True, exist_ok=True)

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
        # 将记录文件名存入 session，供生图回写使用
        session['game']['record_filename'] = filename
        session.modified = True
        print(f'[Record] 已保存: {filepath}')
        return True, ''
    except Exception as e:
        print(f'[Record] 保存失败: {e}')
        return False, str(e)


def update_record_image(filename, image_url):
    """生图成功后回写记录文件的 generated_image 字段"""
    records_dir = RECORDS_DIR
    filepath = records_dir / filename
    if not filepath.exists():
        return False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['generated_image'] = image_url
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _records_cache['data'] = None
        _records_cache['mtime'] = 0
        print(f'[Record] 已更新图片: {filename}')
        return True
    except Exception as e:
        print(f'[Record] 更新图片失败: {e}')
        return False


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
