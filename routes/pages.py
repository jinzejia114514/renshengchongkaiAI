# -*- coding: utf-8 -*-
"""
页面路由 — 首页、世界详情、身份设定、天赋、属性、预览、游戏、结局、记录、关于
"""

from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, session, current_app, send_from_directory

from game_data import WORLDS, GENDERS, RACES
from world_tags import get_world_tags
from game_utils import (
    check_entry, get_world, draw_talents, apply_talents_to_traits
)

pages_bp = Blueprint('pages', __name__)


def _get_llm_client():
    """获取 llm_client 实例（从 app 上下文）"""
    return current_app.llm_client

def _get_llm_config():
    """获取 LLM_CONFIG"""
    return current_app.LLM_CONFIG


@pages_bp.route('/')
def index():
    """首页 - 显示世界选择界面"""
    session['entry_origin'] = 'home'
    return render_template('index.html', worlds=WORLDS)


@pages_bp.route('/easter')
def easter_egg():
    """彩蛋页 - 连点标题 5 次触发首页元素重力掉落（兼容手机陀螺仪）"""
    return send_from_directory(current_app.static_folder, 'easter_egg.html')


@pages_bp.route('/custom')
def custom_world():
    """自定义世界创建页面"""
    session['entry_origin'] = 'home'
    return render_template('custom.html')


@pages_bp.route('/world/random')
def random_world_detail():
    """展示 LLM 生成的随机世界"""
    world = session.get('custom_world')
    if not world:
        return render_template('error.html', message='请先生成随机世界 🎲', back_url='/'), 400
    session['entry_origin'] = 'home'
    return render_template('world.html', world=world, world_tags=None, is_random=True)


@pages_bp.route('/world/<world_id>')
def world_detail(world_id):
    """世界详情页 - 开始游戏前的设定页"""
    session['entry_origin'] = 'home'
    if world_id == 'blue_archive':
        return render_template('blue_archive.html')
    if world_id == 'custom':
        return render_template('error.html', message='自定义世界请从首页创建 🌐', back_url='/'), 400
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404
    return render_template('world.html', world=world, world_tags=None)


@pages_bp.route('/game/custom/identity', methods=['GET', 'POST'])
def custom_game_identity():
    """自定义世界的身份设定"""
    if request.method == 'GET':
        name = request.args.get('name', '自定义世界')
        desc = request.args.get('desc', '你想象中的世界')
        raw_traits = request.args.get('traits', '')
        traits_list = [t.strip() for t in raw_traits.split(',') if t.strip()] if raw_traits else ['体质', '智力', '魅力', '运气']
        world = {
            'id': 'custom', 'icon': '🌐', 'name': name, 'description': desc,
            'color': '#6366f1', 'unlocked': True, 'traits': traits_list,
            'trait_max': 10, 'trait_total': 12, 'use_llm': True,
            'prompt': f'你是一个小说叙事者。玩家在"{name}"世界开始了人生。世界观描述：{desc}。请根据这个设定生成符合世界观的人生事件。',
        }
        session['custom_world'] = world
        session.modified = True
        return render_template('identity.html', world=world, genders=GENDERS, races=RACES, destinies=[])

    if request.method == 'POST':
        data = request.json
        custom_race = data.get('custom_race', '').strip()
        custom_race_desc = data.get('custom_race_desc', '').strip()
        race_obj = None
        if custom_race:
            race_obj = {'id': 'custom', 'name': custom_race, 'icon': '✨', 'unlocked': True}
            if custom_race_desc:
                race_obj['desc'] = custom_race_desc
        # 新建游戏，重置所有进度字段（避免上一个世界的数据残留）
        session['game'] = {
            'world_id': 'custom',
            'gender': next((g for g in GENDERS if g['id'] == data.get('gender')), GENDERS[0]),
            'race': race_obj or next((r for r in RACES if r['id'] == data.get('race')), RACES[0]),
            'custom_race': custom_race if custom_race else None,
            'custom_race_desc': custom_race_desc if custom_race_desc else None,
            'custom_destiny': data.get('custom_destiny', '').strip() or None,
            'talents': None, 'traits': None, 'background': None,
            'history': [], 'current_year': 0, 'step': 'identity_done',
            'player_name': session.get('game', {}).get('player_name', ''),
            'show_record': session.get('game', {}).get('show_record', True),
        }
        session.modified = True
        return jsonify({'status': 'ok', 'next_step': '/game/custom/talents'})
    return '', 405


@pages_bp.route('/game/<world_id>/quickstart', methods=['GET', 'POST'])
def game_quickstart(world_id):
    """快速开始（蔚蓝档案子世界）"""
    if not check_entry():
        return render_template("error.html", message="请从首页开始游戏 🏠", back_url="/"), 403
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404

    if request.method == 'POST':
        data = request.json or {}
        session['game']['traits'] = data.get('traits', {})
        session['game']['step'] = 'traits_done'
        return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/preview'})

    session['game'] = {
        'world_id': world_id,
        'gender': {'id': 'male', 'name': '老师', 'icon': '👤'},
        'race': {'id': 'human', 'name': '人类', 'icon': '👤', 'unlocked': True},
        'talents': [],
        'step': 'talents_done',
        'player_name': session.get('game', {}).get('player_name', ''),
        'show_record': session.get('game', {}).get('show_record', True),
    }
    wt = dict(get_world_tags(world)) if get_world_tags(world) else {}
    if wt:
        session['game']['world_tags'] = wt
    return render_template('traits.html', world=world, talents=[])


@pages_bp.route('/game/<world_id>/start', methods=['POST'])
def game_start(world_id):
    """从世界详情页开始，存储用户名并跳转"""
    if not check_entry():
        return jsonify({"error": "请从首页开始游戏 🏠"}), 403
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return jsonify({'error': '这个世界尚未解锁 🔒'}), 400

    data = request.json or {}
    pn = (data.get('player_name', '') or '')[:12]
    show_record = data.get('show_record', True)
    session['game'] = {
        'world_id': world_id, 'gender': None, 'race': None, 'talents': None,
        'traits': None, 'background': None, 'step': 'not_started',
        'history': [], 'player_name': pn, 'show_record': show_record,
    }
    session['entry_origin'] = 'home'
    next_step = '/game/' + world_id + '/quickstart' if world.get('parent') else '/game/' + world_id + '/identity'
    return jsonify({'status': 'ok', 'next_step': next_step})


@pages_bp.route('/game/random/start', methods=['POST'])
def game_random_start():
    """从随机世界开始"""
    if not check_entry():
        return jsonify({"error": "请从首页开始游戏 🏠"}), 403
    world = session.get('custom_world')
    if not world:
        return jsonify({'error': '请先生成随机世界 🎲'}), 400

    data = request.json or {}
    pn = (data.get('player_name', '') or '')[:12]
    show_record = data.get('show_record', True)
    session['game'] = {
        'world_id': 'random', 'world_name': world.get('name', '随机世界'),
        'custom_world': world, 'gender': None, 'race': None, 'talents': None,
        'traits': None, 'background': None, 'step': 'not_started',
        'history': [], 'player_name': pn, 'show_record': show_record,
    }
    session['entry_origin'] = 'home'
    return jsonify({'status': 'ok', 'next_step': '/game/custom/identity'})


@pages_bp.route('/game/<world_id>/identity', methods=['GET', 'POST'])
def game_identity(world_id):
    """身份设定页面"""
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404

    if request.method == 'POST':
        data = request.json
        custom_race = data.get('custom_race', '').strip()
        custom_race_desc = data.get('custom_race_desc', '').strip()
        race_obj = None
        if custom_race:
            race_obj = {'id': 'custom', 'name': custom_race, 'icon': '✨', 'unlocked': True}
            if custom_race_desc:
                race_obj['desc'] = custom_race_desc
        session['game'].update({
            'world_id': world_id,
            'gender': next((g for g in GENDERS if g['id'] == data.get('gender')), GENDERS[0]),
            'race': race_obj or next((r for r in RACES if r['id'] == data.get('race')), RACES[0]),
            'custom_race': custom_race if custom_race else None,
            'custom_race_desc': custom_race_desc if custom_race_desc else None,
            'custom_destiny': data.get('custom_destiny', '').strip() or None,
            'step': 'identity_done'
        })
        return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/talents'})

    return render_template('identity.html', world=world, genders=GENDERS, races=RACES, destinies=[])


@pages_bp.route('/game/<world_id>/talents', methods=['GET', 'POST'])
def game_talents(world_id):
    """天赋抽取页面"""
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404
    if 'game' not in session or not session['game'].get('gender'):
        return render_template('error.html', message='请先设定身份 🎭', back_url='/game/' + world_id + '/identity'), 400

    if request.method == 'POST':
        data = request.json
        if data.get('action') == 'draw':
            talents = draw_talents(3)
            session['game']['talent_pool'] = talents
            session['game']['rerolls_left'] = 3
            return jsonify({'talents': talents, 'rerolls_left': 3})
        elif data.get('action') == 'reroll':
            rerolls_left = session['game'].get('rerolls_left', 0)
            if rerolls_left > 0:
                talents = draw_talents(3)
                session['game']['talent_pool'] = talents
                session['game']['rerolls_left'] = rerolls_left - 1
                return jsonify({'talents': talents, 'rerolls_left': rerolls_left - 1})
            return jsonify({'status': 'error', 'message': '没有重抽次数了'})
        elif data.get('action') == 'confirm':
            talent_ids = data.get('talent_ids', [])
            talents = [t for t in session['game'].get('talent_pool', []) if t['id'] in talent_ids]
            session['game']['talents'] = talents
            session['game']['step'] = 'talents_done'
            return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/traits'})

    return render_template('talents.html', world=world)


@pages_bp.route('/game/<world_id>/traits', methods=['GET', 'POST'])
def game_traits(world_id):
    """属性分配页面"""
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404
    if session.get('game', {}).get('talents') is None:
        return render_template('error.html', message='请先抽取天赋 ✦', back_url='/game/' + world_id + '/talents'), 400

    if request.method == 'POST':
        data = request.json
        traits = data.get('traits', {})
        talents = session['game'].get('talents', [])
        traits = apply_talents_to_traits(traits, talents)
        session['game']['traits'] = traits
        session['game']['step'] = 'traits_done'
        return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/preview'})

    return render_template('traits.html', world=world, talents=session['game'].get('talents', []))


@pages_bp.route('/game/<world_id>/preview', methods=['GET', 'POST'])
def game_preview(world_id):
    """命运预览页面"""
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404

    game = session.get('game', {})
    if not game.get('traits') or game.get('talents') is None:
        return render_template('error.html', message='请先完成身份设定、天赋抽取和属性分配再来预览 ✨', back_url='/game/' + world_id + '/identity'), 400

    llm_client = _get_llm_client()

    # 身世与世界书只用生成一次
    if not game.get('background'):
        background = None
        generated_tags = None

        if world.get('time_unit') == '周':
            if world_id.find('abydos') >= 0:
                background = '你是夏莱的老师，接到了阿拜多斯对策委员会的求助信。这所濒临废校的学校背负着巨额债务，仅剩五名学生还在坚持。你决定前往阿拜多斯自治区。'
            elif world_id.find('gamedev') >= 0:
                background = '你是夏莱的老师，游戏开发部向夏莱发出了求助信。这个即将被废部的社团只有三名成员，她们开发的游戏被评为年度最烂。你决定前往千年科技学院。'
            else:
                background = '你来到了基沃托斯，作为夏莱的老师，新的故事即将开始。'
        elif llm_client.enabled or (session.get('llm_override') and session['llm_override'].get('enabled')):
            bg_result = llm_client.generate_background(world, game, session.get('llm_override'))
            if isinstance(bg_result, dict) and '_error' in bg_result:
                background = f"[LLM 生成错误] {bg_result['_error']}"
                if bg_result.get('_raw'):
                    background += f"\n原始返回: {bg_result['_raw'][:200]}"
                generated_tags = None
            elif isinstance(bg_result, dict):
                background = bg_result.get('background', '')
                generated_tags = bg_result.get('world_tags')
            elif isinstance(bg_result, str):
                background = bg_result

        if not background:
            background = "你出生在一个普通的家庭，从小就表现出一些与众不同的特质。"

        session['game']['background'] = background
        if generated_tags and isinstance(generated_tags, dict):
            session['game']['world_tags'] = generated_tags
            game['world_tags'] = generated_tags
    else:
        background = game['background']

    if request.method == 'POST':
        session['game']['current_year'] = 0
        session['game']['history'] = []
        if not game.get('world_tags'):
            wt = dict(get_world_tags(world)) if get_world_tags(world) else {}
            if wt:
                session['game']['world_tags'] = wt
        session['game']['step'] = 'playing'
        return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/play'})

    wt = game.get('world_tags') or get_world_tags(world)
    return render_template('preview.html', world=world, game=game, background=background, world_tags=wt)


@pages_bp.route('/game/<world_id>/play')
def game_play(world_id):
    """游戏主页面"""
    world = get_world(world_id)
    if not world or not world['unlocked']:
        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404
    if session.get('game', {}).get('step') != 'playing':
        return render_template('error.html', message='请先完成命运预览，再开始人生 🚀', back_url='/game/' + world_id + '/preview'), 400

    game = session.get('game', {})
    if world_id == 'random' and not game.get('custom_world'):
        game['custom_world'] = world
        session['game'] = game

    wt = game.get('world_tags') or get_world_tags(world)
    return render_template('game.html', world=world, game=game, world_tags=wt)


@pages_bp.route('/game/<world_id>/ending')
def game_ending(world_id):
    """结局页面 - 展示完整人生回顾"""
    if not check_entry():
        return render_template("error.html", message="请从首页开始游戏 🏠", back_url="/"), 403

    world = get_world(world_id)
    game = session.get('game', {})
    ending = game.get('ending', {'type': 'normal', 'title': '一生结束', 'text': '你的故事落幕了.'})
    history = game.get('history', [])
    traits = game.get('traits', {})
    talents = game.get('talents', [])
    background = game.get('background', '')

    if history:
        years = [h['year'] for h in history if 'year' in h]
        if years:
            lifespan = max(years) - min(years)
            if lifespan > 0:
                ending['lifespan'] = lifespan

    return render_template('ending.html',
        world=world, ending=ending, history=history, traits=traits,
        talents=talents, background=background, world_tags=game.get('world_tags', {}),
        relationships=game.get('relationships', []),
        inventory=game.get('inventory', []),
        conditions=game.get('conditions', []),
        journal=game.get('journal', []),
        time_unit=world.get('time_unit', '岁') if world else '岁')


@pages_bp.route('/game/export', methods=['GET'])
def export_record():
    """导出人生记录"""
    game = session.get('game', {})
    history = game.get('history', [])
    if not game or not history:
        return render_template('error.html', message='没有可导出的记录'), 400

    world = next((w for w in WORLDS if w['id'] == game.get('world_id')), {'name': '未知世界'})
    gender = game.get('gender', {}).get('name', '未知')
    race = game.get('race', {}).get('name', '未知')
    talents = game.get('talents', [])
    traits = game.get('traits', {})
    background = game.get('background', '')

    export_text = []
    export_text.append("=" * 60)
    export_text.append("                    AI 人生重开手帐")
    export_text.append("=" * 60)
    export_text.append("")
    export_text.append(f"【世界】{world['name']}")
    export_text.append(f"【性别】{gender}")
    export_text.append(f"【种族】{race}")
    export_text.append("")

    if talents:
        export_text.append("【天赋】")
        for talent in talents:
            export_text.append(f"  · {talent['name']}")
        export_text.append("")

    if traits:
        export_text.append("【属性】")
        for trait, value in traits.items():
            export_text.append(f"  {trait}: {value}")
        export_text.append("")

    if background:
        export_text.append("【身世】")
        export_text.append(background)
        export_text.append("")

    # 人物关系
    relationships = game.get('relationships', [])
    if relationships:
        export_text.append("【人物关系】")
        for r in relationships:
            rel_text = f"{r.get('name', '?')} - {r.get('relation', '陌生人')} (亲密度:{r.get('affinity', 50)}·{r.get('status', '中立')})"
            export_text.append(f"  · {rel_text}")
        export_text.append("")

    # 物品栏
    inventory = game.get('inventory', [])
    if inventory:
        export_text.append("【物品栏】")
        for item in inventory:
            export_text.append(f"  · {item.get('name', '?')} ({item.get('type', 'misc')}){': ' + item.get('desc', '') if item.get('desc') else ''}")
        export_text.append("")

    # 事件日志
    journal = game.get('journal', [])
    if journal:
        export_text.append("【关键事件】")
        for entry in journal:
            tags_str = f' [{", ".join(entry.get("tags", []))}]' if entry.get('tags') else ''
            export_text.append(f"  · {entry.get('year', '?')}岁 - {entry.get('title', '?')}{tags_str}")
        export_text.append("")

    export_text.append("【人生纪事】")
    time_unit = world.get('time_unit', '岁')
    for record in history:
        event_text = record.get('event', '')
        choice_text = record.get('choice', '')
        year = record.get('year', '')
        tc = record.get('trait_changes', {}) or {}
        wtc = record.get('world_tag_changes', {}) or {}
        extra = []
        if tc:
            for k, v in tc.items():
                extra.append(f'{k}{"+" if v > 0 else ""}{v}')
        if wtc:
            for k, v in wtc.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        if sv == 0 or sv is None:
                            continue
                        extra.append(f'{k}.{sk}: {"+" if sv > 0 else ""}{sv}')
                elif v != 0 and v is not None:
                    extra.append(f'{k}: {v}')
        extra_str = f'  [{", ".join(extra)}]' if extra else ''
        export_text.append(f"{year:3d} {time_unit}: {event_text}{extra_str}")
        if choice_text:
            export_text.append(f"       选择：{choice_text}")

    if 'ending' in game:
        export_text.append("")
        export_text.append("【结局】")
        export_text.append(f"{game['ending']['title']}")
        export_text.append(f"{game['ending']['text']}")

    export_text.append("")
    export_text.append("=" * 60)
    export_text.append(f"   记录生成于 {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    export_text.append("=" * 60)

    export_json = {
        'world': world['name'], 'gender': gender, 'race': race,
        'talents': [t['name'] for t in talents], 'traits': traits,
        'background': background, 'history': history,
        'world_tags': game.get('world_tags', {}),
        'relationships': game.get('relationships', []),
        'inventory': game.get('inventory', []),
        'conditions': game.get('conditions', []),
        'journal': game.get('journal', []),
        'time_unit': world.get('time_unit', '岁'),
        'ending': game.get('ending'),
        'generated_at': datetime.now().isoformat()
    }

    return jsonify({'text': '\n'.join(export_text), 'json': export_json})


@pages_bp.route('/records')
def records_page():
    """历史记录页面"""
    session['entry_origin'] = 'home'
    return render_template('records.html')


@pages_bp.route('/about')
def about():
    """关于页面"""
    llm_client = _get_llm_client()
    llm_config = _get_llm_config()
    return render_template('about.html', llm_config=llm_config, llm_enabled=llm_client.enabled)
