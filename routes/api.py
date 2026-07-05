# -*- coding: utf-8 -*-
"""
API 路由 — LLM 交互、存档、记录查询
"""

import json
from datetime import datetime
from pathlib import Path

from flask import Blueprint, request, jsonify, session, current_app

from game_utils import (
    check_entry, get_world, get_age_icon, get_records_list, save_game_record
)
from world_tags import _merge_world_tag_changes, _clean_world_tags


def _filter_zero_changes(changes):
    """过滤掉值为0的标签变化（LLM可能错误返回无变化的标签）"""
    if not changes or not isinstance(changes, dict):
        return changes
    filtered = {}
    for key, val in changes.items():
        if isinstance(val, dict):
            inner = {}
            for k, v in val.items():
                if v is None or (isinstance(v, (int, float)) and v != 0):
                    inner[k] = v
            if inner:
                filtered[key] = inner
        elif val is None or (isinstance(val, (int, float)) and val != 0):
            filtered[key] = val
    return filtered

api_bp = Blueprint('api', __name__)


def _get_llm_client():
    """获取 llm_client 实例（从 app 上下文）"""
    return current_app.llm_client


def _get_llm_config():
    """获取 LLM_CONFIG"""
    return current_app.LLM_CONFIG


@api_bp.route('/api/random-world', methods=['POST'])
def api_random_world():
    """使用 LLM 生成一个随机世界"""
    llm_client = _get_llm_client()
    LLM_CONFIG = _get_llm_config()

    override = session.get('llm_override')
    enabled = llm_client.enabled or (override and override.get('enabled'))
    if not enabled:
        return jsonify({'error': '请先启用 LLM 设置'}), 400

    try:
        system_prompt = """你是一个创意世界观生成器。生成一个独特的虚构世界观，用于人生模拟游戏。
要求：
- 世界观要有创意，可以是科幻、奇幻、武侠、废土、赛博朋克、克苏鲁、修仙、校园、末日等任意题材
- 不要与常见作品完全重复，要有自己的特色
- 属性（traits）为 4 个，每个属性名 2-4 字，适合该世界观
- 颜色使用十六进制格式（如 #4a6fa5）
- 图标使用单个 emoji
以JSON格式返回：
{
    "name": "世界名称（4-8字）",
    "icon": "emoji图标",
    "description": "一句话描述（20字内）",
    "color": "#hexcolor",
    "traits": ["属性1", "属性2", "属性3", "属性4"],
    "preview": "世界预览（50字左右，描述这个世界的基本背景）",
    "prompt": "详细的叙事者提示词（200-300字），描述世界观设定、核心冲突、叙事风格、事件生成规则。要求使用第二人称「你」，每个事件附带属性变化trait_changes（4个属性），范围-2到+2。"
}"""

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': '请生成一个独特的虚构世界观：'}
        ]

        if override:
            creative_override = dict(override)
        else:
            creative_override = {
                'enabled': True,
                'api_base': LLM_CONFIG.get('api_base', ''),
                'api_key': LLM_CONFIG.get('api_key', ''),
                'model': LLM_CONFIG.get('model', ''),
            }
        creative_override['enabled'] = True

        response = llm_client._make_request(messages, creative_override)
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            try:
                data = json.loads(content)
            except:
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(content[json_start:json_end])
                else:
                    return jsonify({'error': '生成失败，无法解析'}), 500

            world_name = str(data.get('name', '随机世界')).strip() or '随机世界'
            world = {
                'id': 'random', 'icon': str(data.get('icon', '🌍')).strip() or '🌍',
                'name': world_name,
                'description': str(data.get('description', '一个神秘的世界')).strip(),
                'color': str(data.get('color', '#6366f1')).strip(),
                'unlocked': True,
                'traits': data.get('traits', ['力量', '智慧', '勇气', '运气']),
                'trait_max': 10, 'trait_total': 12, 'use_llm': True,
                'preview': str(data.get('preview', '')).strip(),
                'prompt': str(data.get('prompt', '')).strip(),
            }
            session['custom_world'] = world
            return jsonify({'status': 'ok', 'world': world})
        else:
            return jsonify({'error': f'API 错误: {response.status_code}'}), 500
    except Exception as e:
        return jsonify({'error': f'生成失败: {str(e)}'}), 500


@api_bp.route('/game/<world_id>/next', methods=['POST'])
def game_next(world_id):
    """下一个事件 — LLM决定寿命"""
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return jsonify({'error': '世界未解锁'}), 400

    game = session.get('game', {})
    if not game or game.get('step') != 'playing':
        return jsonify({'error': '游戏未开始'}), 400

    llm_client = _get_llm_client()
    current_year = game.get('current_year', 0)
    llm_result = None
    llm_override = session.get('llm_override')
    llm_error = ""

    enabled = llm_client.enabled or (session.get('llm_override') and session['llm_override'].get('enabled'))
    if enabled and world.get('use_llm'):
        # 调试：打印传入 LLM 的新系统数据
        print(f'[DEBUG] 传入 LLM - relationships: {len(game.get("relationships", []))}, inventory: {len(game.get("inventory", []))}, conditions: {len(game.get("conditions", []))}, journal: {len(game.get("journal", []))}')
        llm_result = llm_client.generate_events_batch(world, game, llm_override)
        # 调试：打印 LLM 返回的新系统数据
        if llm_result:
            print(f'[DEBUG] LLM 返回 - relationship_changes: {llm_result.get("relationship_changes", [])}, journal_entries: {llm_result.get("journal_entries", [])}')

    events_data = []
    choices = []
    is_ended = False
    record_saved = None
    record_message = ''
    ending = None
    fortune = 100

    if llm_result and 'events' in llm_result and 'choices' in llm_result:
        events = llm_result['events']
        choices = llm_result['choices']

        if 'fortune' in llm_result:
            try:
                fortune = max(0, min(100, int(llm_result['fortune'])))
            except (ValueError, TypeError):
                fortune = 50

        finished = llm_result.get('finished', 'false')
        epitaph = llm_result.get('epitaph', '')

        for i, evt in enumerate(events):
            year = evt.get('year')
            if not year or year <= current_year:
                year = current_year + 1 + i
            tc = evt.get('trait_changes', {}) or {}
            events_data.append({
                'year': year, 'event': evt['text'],
                'age_icon': get_age_icon(year), 'trait_changes': tc
            })

        wtc = _filter_zero_changes(llm_result.get('world_tag_changes', {}) or {})
        if wtc and events_data:
            events_data[-1]['world_tag_changes'] = wtc
        game_tags = game.get('world_tags', {})
        if not isinstance(game_tags, dict):
            game_tags = {}
        wtc = _filter_zero_changes(llm_result.get('world_tag_changes', {}) or {})
        if wtc:
            print(f'[LLM] world_tag_changes raw: {json.dumps(wtc, ensure_ascii=False)}')
            _merge_world_tag_changes(game_tags, wtc)
            game_tags = _clean_world_tags(game_tags)
            session['game']['world_tags'] = game_tags
            print(f'[LLM] world_tags merged: {json.dumps(game_tags, ensure_ascii=False, indent=2)}')

        # 人物关系变化
        rel_changes = llm_result.get('relationship_changes', []) or []
        if rel_changes:
            relationships = game.get('relationships', [])
            for change in rel_changes:
                if change.get('action') == 'remove':
                    relationships = [r for r in relationships if r.get('name') != change.get('name')]
                else:
                    existing = next((r for r in relationships if r.get('name') == change.get('name')), None)
                    if existing:
                        if 'affinity_change' in change:
                            existing['affinity'] = max(0, min(100, existing.get('affinity', 50) + change['affinity_change']))
                        if 'status' in change:
                            existing['status'] = change['status']
                        if 'relation' in change:
                            existing['relation'] = change['relation']
                    else:
                        relationships.append({
                            'name': change.get('name', '未知'),
                            'relation': change.get('relation', '陌生人'),
                            'affinity': max(0, min(100, change.get('affinity', 50))),
                            'status': change.get('status', '中立'),
                            'desc': change.get('desc', '')
                        })
            session['game']['relationships'] = relationships
            print(f'[LLM] relationships updated: {len(relationships)} NPCs')

        # 物品栏变化
        inv_changes = llm_result.get('inventory_changes', []) or []
        if inv_changes:
            inventory = game.get('inventory', [])
            for change in inv_changes:
                if change.get('action') == 'use' or change.get('action') == 'remove':
                    inventory = [i for i in inventory if i.get('name') != change.get('name')]
                else:
                    if not any(i.get('name') == change.get('name') for i in inventory):
                        inventory.append({
                            'name': change.get('name', '未知物品'),
                            'type': change.get('type', 'misc'),
                            'desc': change.get('desc', ''),
                            'effect': change.get('effect', '')
                        })
            session['game']['inventory'] = inventory
            print(f'[LLM] inventory updated: {len(inventory)} items')

        # 状态效果变化
        cond_changes = llm_result.get('condition_changes', []) or []
        if cond_changes:
            conditions = game.get('conditions', [])
            for change in cond_changes:
                if change.get('action') == 'remove':
                    conditions = [c for c in conditions if c.get('name') != change.get('name')]
                else:
                    existing = next((c for c in conditions if c.get('name') == change.get('name')), None)
                    if existing:
                        existing['duration'] = change.get('duration', existing.get('duration', -1))
                        existing['desc'] = change.get('desc', existing.get('desc', ''))
                    else:
                        conditions.append({
                            'name': change.get('name', '未知状态'),
                            'type': change.get('type', 'neutral'),
                            'duration': change.get('duration', -1),
                            'desc': change.get('desc', '')
                        })
            session['game']['conditions'] = conditions
            print(f'[LLM] conditions updated: {len(conditions)} effects')

        # 事件日志
        journal_entries = llm_result.get('journal_entries', []) or []
        if journal_entries:
            journal = game.get('journal', [])
            for entry in journal_entries:
                journal.append({
                    'year': current_year + 1,
                    'title': entry.get('title', '未命名事件'),
                    'importance': entry.get('importance', 'normal'),
                    'tags': entry.get('tags', [])
                })
            session['game']['journal'] = journal
            print(f'[LLM] journal updated: {len(journal)} entries')

        if finished and finished != "false":
            is_ended = True
            ending = {
                'type': finished, 'title': '一生结束',
                'text': epitaph or '你走完了这一生。'
            }
            print(f'[DEBUG] ending 初始化: type={finished}, text={ending["text"][:50]}...')
    else:
        llm_error = "LLM 生成失败，请稍后重试"

    # 保存事件历史
    game['history'] = game.get('history', [])
    for evt_data in events_data:
        game['history'].append({
            'year': evt_data['year'], 'event': evt_data['event'],
            'choice': None, 'trait_changes': evt_data.get('trait_changes', {}),
            'world_tag_changes': evt_data.get('world_tag_changes', {}),
            'age_icon': evt_data.get('age_icon', '')
        })
        game['current_year'] = evt_data['year']
        changes = evt_data.get('trait_changes', {}) or {}
        for trait, delta in changes.items():
            if trait in game.get('traits', {}):
                game['traits'][trait] = max(0, game['traits'][trait] + delta)

    game['pending_choices'] = choices
    session['game'] = game

    if is_ended:
        session['game']['step'] = 'ended'
        eval_result = None
        if llm_client.enabled or (session.get('llm_override') and session['llm_override'].get('enabled')):
            eval_result = llm_client.generate_ending_evaluation(world, game, session.get('llm_override'))
        if eval_result:
            print(f'[DEBUG] eval_result: {json.dumps(eval_result, ensure_ascii=False)[:200]}')
            ending['score'] = eval_result.get('score', 0)
            ending['summary'] = eval_result.get('summary', '')
            ending['type'] = eval_result.get('type', 'normal')
            ending['title'] = eval_result.get('title', '一生结束')
            if not ending.get('text'):
                ending['text'] = eval_result.get('epitaph', '你走完了这一生。')
            print(f'[DEBUG] ending 最终: score={ending["score"]}, title={ending["title"]}, summary={ending["summary"][:30]}...')
        session['game']['ending'] = ending
        record_saved, record_message = save_game_record(world, game, ending, llm_client)

    return jsonify({
        'events': events_data, 'choices': choices if not is_ended else [],
        'ended': is_ended, 'llm_error': llm_error if llm_error else None,
        'retry': bool(llm_error), 'fortune': fortune,
        'world_tags': session.get('game', {}).get('world_tags'),
        'relationships': session.get('game', {}).get('relationships', []),
        'inventory': session.get('game', {}).get('inventory', []),
        'conditions': session.get('game', {}).get('conditions', []),
        'journal': session.get('game', {}).get('journal', []),
        'record_saved': record_saved, 'record_message': record_message
    })


@api_bp.route('/game/<world_id>/choose', methods=['POST'])
def game_choose(world_id):
    """玩家做出选择"""
    if not check_entry():
        return jsonify({"error": "请从首页开始"}), 403
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return jsonify({'error': '世界未解锁'}), 400

    game = session.get('game', {})
    if not game or game.get('step') != 'playing':
        return jsonify({'error': '游戏未开始'}), 400

    data = request.json
    choice_idx = data.get('choice', 0)
    choice_text = data.get('custom_text', '')
    choices = game.get('pending_choices', [])

    final_choice = ''
    if choice_idx == 3 and choice_text:
        final_choice = choice_text
    elif 0 <= choice_idx < len(choices):
        final_choice = choices[choice_idx]['text']

    if final_choice:
        game['last_choice'] = final_choice
        history = game.get('history', [])
        if history:
            history[-1]['choice'] = final_choice
        game['pending_choices'] = []

    session['game'] = game
    return jsonify({'status': 'ok'})


@api_bp.route('/game/save', methods=['GET'])
def save_game():
    """导出当前游戏存档为JSON"""
    game = session.get('game', {})
    world_id = game.get('world_id', '')
    world = get_world(world_id) or {}
    history = game.get('history', [])
    if not game or not history:
        return jsonify({'error': '没有可保存的游戏进度'}), 400

    save_data = {
        'version': 1, 'saved_at': datetime.now().isoformat(),
        'world_id': world_id, 'world_name': world.get('name', '未知'),
        'player_name': game.get('player_name', ''),
        'gender': game.get('gender', {}), 'race': game.get('race', {}),
        'custom_race': game.get('custom_race', ''),
        'custom_race_desc': game.get('custom_race_desc', ''),
        'custom_destiny': game.get('custom_destiny', ''),
        'talents': game.get('talents', []), 'traits': game.get('traits', {}),
        'background': game.get('background', ''),
        'current_year': game.get('current_year', 0),
        'history': game.get('history', []),
        'world_tags': game.get('world_tags', {}),
        'relationships': game.get('relationships', []),
        'inventory': game.get('inventory', []),
        'conditions': game.get('conditions', []),
        'journal': game.get('journal', []),
        'step': game.get('step', 'playing'),
    }
    if history and not history[-1].get('choice'):
        save_data['pending_choices'] = game.get('pending_choices', [])
    else:
        save_data['pending_choices'] = []
    return jsonify(save_data)


@api_bp.route('/game/load', methods=['POST'])
def load_game():
    """从JSON文件导入游戏存档"""
    if 'file' not in request.files:
        return jsonify({'error': '请上传存档文件'}), 400
    try:
        data = json.loads(request.files['file'].read().decode('utf-8'))
        if data.get('version') != 1:
            return jsonify({'error': '存档版本不兼容'}), 400
        session['game'] = {
            'world_id': data.get('world_id', ''),
            'player_name': data.get('player_name', ''),
            'gender': data.get('gender', {}), 'race': data.get('race', {}),
            'custom_race': data.get('custom_race', ''),
            'custom_race_desc': data.get('custom_race_desc', ''),
            'custom_destiny': data.get('custom_destiny', ''),
            'talents': data.get('talents', []), 'traits': data.get('traits', {}),
            'background': data.get('background', ''),
            'current_year': data.get('current_year', 0),
            'history': data.get('history', []),
            'world_tags': data.get('world_tags', {}),
            'relationships': data.get('relationships', []),
            'inventory': data.get('inventory', []),
            'conditions': data.get('conditions', []),
            'journal': data.get('journal', []),
            'step': 'playing', 'show_record': True,
            'pending_choices': data.get('pending_choices', []),
        }
        session['entry_origin'] = 'home'
        return jsonify({'status': 'ok', 'next_step': '/game/' + data.get('world_id', '') + '/play'})
    except Exception as e:
        return jsonify({'error': f'存档读取失败: {e}'}), 400


@api_bp.route('/game/load-json', methods=['POST'])
def load_game_json():
    """从前端 localStorage 的 JSON 数据恢复存档"""
    data = request.json or {}
    if data.get('version') != 1:
        return jsonify({'error': '存档版本不兼容'}), 400
    try:
        session['game'] = {
            'world_id': data.get('world_id', ''),
            'player_name': data.get('player_name', ''),
            'gender': data.get('gender', {}), 'race': data.get('race', {}),
            'custom_race': data.get('custom_race', ''),
            'custom_race_desc': data.get('custom_race_desc', ''),
            'custom_destiny': data.get('custom_destiny', ''),
            'talents': data.get('talents', []), 'traits': data.get('traits', {}),
            'background': data.get('background', ''),
            'current_year': data.get('current_year', 0),
            'history': data.get('history', []),
            'world_tags': data.get('world_tags', {}),
            'relationships': data.get('relationships', []),
            'inventory': data.get('inventory', []),
            'conditions': data.get('conditions', []),
            'journal': data.get('journal', []),
            'step': 'playing', 'show_record': True,
            'pending_choices': data.get('pending_choices', []),
        }
        session['entry_origin'] = 'home'
        return jsonify({'status': 'ok', 'next_step': '/game/' + data.get('world_id', '') + '/play'})
    except Exception as e:
        return jsonify({'error': f'存档读取失败: {e}'}), 400


@api_bp.route('/api/llm-config', methods=['POST'])
def api_llm_config():
    """前端传入 LLM 设置，存到当前 session"""
    llm_client = _get_llm_client()

    data = request.json or {}
    on = data.get('enabled', False) and bool(data.get('api_key', '').strip())
    override = {'enabled': on}

    for key in ['event_words', 'writing_style']:
        v = data.get(key)
        if v:
            override[key] = v.strip()
    for key, cast in [('max_tokens', int), ('batch_min', int), ('batch_max', int)]:
        raw = data.get(key)
        if raw is not None:
            try:
                override[key] = cast(raw)
            except:
                pass

    if on:
        for key in ['api_base', 'api_key', 'model']:
            v = data.get(key)
            if v:
                override[key] = v.strip()
        for key, cast in [('temperature', float), ('top_p', float)]:
            raw = data.get(key)
            if raw is not None:
                try:
                    override[key] = cast(raw)
                except:
                    pass
        custom_body = dict(llm_client.custom_body)
        if data.get('json_mode'):
            custom_body['response_format'] = {'type': 'json_object'}
        raw_body = data.get('custom_body')
        if raw_body:
            try:
                frontend_body = json.loads(raw_body)
                custom_body.update(frontend_body)
            except json.JSONDecodeError:
                pass
        override['custom_request_body'] = custom_body

    # 实验性功能：使用事件日志替代完整历史
    if data.get('use_journal') is not None:
        override['use_journal'] = bool(data.get('use_journal'))

    session['llm_override'] = override
    print(f"[LLM Config] 已更新: on={on}, override_keys={list(override.keys())}")
    return jsonify({'status': 'ok'})


@api_bp.route('/api/records')
def api_records():
    """获取所有公开记录列表"""
    records_dir = Path(__file__).parent.parent / 'records'
    if not records_dir.exists():
        return jsonify([])
    return jsonify(get_records_list(records_dir))


@api_bp.route('/api/records/<path:filename>')
def api_record_detail(filename):
    """获取单条记录详情"""
    records_dir = Path(__file__).parent.parent / 'records'
    filepath = records_dir / filename
    if not filepath.exists() or 'nodisplay' in filename:
        return jsonify({'error': '记录不存在'}), 404
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except:
        return jsonify({'error': '读取失败'}), 500
