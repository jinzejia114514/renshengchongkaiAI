#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

AI 人生重开手帐 - Flask 应用

支持 OpenAI 格式的 LLM 接口

完整游戏流程：身份设定 → 天赋抽取 → 属性分配 → 开始人生

"""

from flask import Flask, render_template, request, jsonify, session

from flask_session import Session

import random

import json

from datetime import datetime, timedelta

import os

from pathlib import Path



try:

    import requests

    HAS_REQUESTS = True

except ImportError:

    HAS_REQUESTS = False





SESSION_DIR = Path(__file__).parent / '.sessions'

SESSION_DIR.mkdir(exist_ok=True)





def load_config():

    """加载配置文件"""

    config_path = Path(__file__).parent / 'config.json'

    if config_path.exists():

        with open(config_path, 'r', encoding='utf-8') as f:

            return json.load(f)

    return {}





CONFIG = load_config()



app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', CONFIG.get('app', {}).get('secret_key', 'ai_life_restart_secret_key_2024'))

app.config['SESSION_TYPE'] = 'filesystem'

app.config['SESSION_FILE_DIR'] = str(SESSION_DIR)

app.config['SESSION_PERMANENT'] = True

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)

Session(app)





def get_trait_icon(trait):

    """获取属性对应的图标"""

    icons = {

        '容貌': '✨', '智力': '🧠', '体质': '💪', '家境': '💰',

        '根骨': '🦴', '悟性': '💡', '气运': '🎲', '心境': '🧘',

        '勇气': '⚔️', '智慧': '📖', '忠诚': '🛡️', '运气': '🍀',

        '魅力': '💫',
        '魔力': '🔮',
        '内力': '🌀',
        '身法': '💨',
        '侠义': '🛡️',

        '战斗': '⚔️', '源石技艺': '🔮', '战术': '🧠', '意志': '🔥',
        '力量': '💪', '谋略': '🎯', '战力': '⚡', '指挥': '📡', '羁绊': '💝',
        '信仰': '🙏', '武勇': '🗡️', '统帅': '🏰', '基因': '🧬', '精神': '🌟',
        '能力': '💎', '理智': '🧠', '感知': '👁️', '仁德': '💝', '天命': '⭐',

    }

    return icons.get(trait, '✨')





def get_trait_desc(trait):

    """获取属性对应的描述"""

    descs = {

        '容貌': '外貌魅力，影响社交和恋爱',

        '智力': '学习能力和认知水平',

        '体质': '身体素质，影响健康和寿命',

        '家境': '家庭经济条件和社会资源',

        '根骨': '修仙的基础资质',

        '悟性': '领悟道法的能力',

        '气运': '运气好坏',

        '心境': '道心稳固程度',

        '勇气': '面对危险时的胆量',

        '智慧': '分析和决策能力',

        '忠诚': '对信仰的坚持程度',

        '魅力': '个人吸引力，影响社交和说服力',

        '魔力': '操控魔法的潜力和掌控力',

        '内力': '体内真气修为，决定武功威力',
        '身法': '身法轻功，影响闪避与行动',
        '侠义': '侠义之心，影响江湖声望和正道关系',

        '战斗': '近身作战能力，影响生存和武力对抗',

        '源石技艺': '操控源石能量的天赋，影响施法能力',

        '战术': '战场局势的判断和指挥能力',

        '意志': '精神的坚韧程度，面对感染和压力的承受力',
        '运气': '命运的眷顾程度，影响机遇和意外',
        '力量': '身体素质与力量，影响战斗和体力',
        '谋略': '谋划和策略能力，影响计策与布局',
        '战力': '综合战斗能力，影响对抗与生存',
        '指挥': '统筹全局、调度团队的能力',
        '羁绊': '与他人的情感纽带深度，影响团队凝聚力',
        '信仰': '对信念的坚守程度，影响意志和号召力',
        '武勇': '个人武力与胆识，影响战斗表现',
        '统帅': '领兵指挥能力，影响大规模作战',
        '基因': '先天天赋与血统，影响成长潜力',
        '精神': '意志力和精神力，影响承受与感知',
        '能力': '综合素质与才干，影响多领域表现',
        '理智': '理性思维与判断力，影响决策质量',
        '感知': '观察力和直觉，影响信息获取',
        '仁德': '仁爱之心与德行，影响人心向背',
        '天命': '命运眷顾程度，影响大势走向',

    }

    return descs.get(trait, '')





app.jinja_env.globals.update(get_trait_icon=get_trait_icon)

app.jinja_env.globals.update(get_trait_desc=get_trait_desc)

app.jinja_env.globals.update(url_for_static=lambda filename: f'/static/{filename}')

@app.context_processor
def inject_globals():
    return dict(request=request)



# 合并配置文件和环境变量

def merge_config():

    config = CONFIG.get('llm', {})

    env_config = {

        'enabled': os.environ.get('LLM_ENABLED', None),

        'api_base': os.environ.get('LLM_API_BASE', None),

        'api_key': os.environ.get('LLM_API_KEY', None),

        'model': os.environ.get('LLM_MODEL', None),

        'temperature': os.environ.get('LLM_TEMPERATURE', None),

        'max_tokens': os.environ.get('LLM_MAX_TOKENS', None),

        'custom_request_body': os.environ.get('LLM_CUSTOM_BODY', None),

    }



    for key, value in env_config.items():

        if value is not None:

            if key == 'enabled':

                config[key] = value.lower() == 'true'

            elif key == 'temperature':

                config[key] = float(value)

            elif key == 'max_tokens':

                config[key] = int(value)

            elif key == 'custom_request_body':

                try:

                    config[key] = json.loads(value)

                except:

                    pass

            else:

                config[key] = value



    if 'enabled' not in config:

        config['enabled'] = False

    if 'api_base' not in config:

        config['api_base'] = 'https://api.openai.com/v1'

    if 'api_key' not in config:

        config['api_key'] = ''

    if 'model' not in config:

        config['model'] = 'gpt-3.5-turbo'

    if 'temperature' not in config:

        config['temperature'] = 0.9

    if 'max_tokens' not in config:

        config['max_tokens'] = 8192

    if 'custom_request_body' not in config:

        config['custom_request_body'] = {}



    return config



LLM_CONFIG = merge_config()




# ============ 世界书标签系统 ============

WORLD_TAG_DEFAULTS = {
    'arknights': {
        '社会结构': {'社会阶层': -7, '政治稳定': -5, '势力密度': 8, '法治程度': -4, '教育水平': 3, '家庭观念': 4},
        '自然环境': {'灾害频率': 8, '气候适宜': 1, '地形多样': 7, '资源丰富': -6},
        '经济体系': {'经济自由': 2, '科技水平': 7, '资源分配': -8, '贸易开放': 3},
        '超自然': {'超自然强度': 8, '普及程度': 7, '危险程度': 9, '可控程度': 3},
        '人口构成': {'种族多样': 7, '人口密度': 3, '语言统一': 6, '文化多元': 7},
        '文化面貌': {'价值观对立': 3, '宗教信仰': 4, '艺术繁荣': 5, '传统保留': 2},
    },
    'warhammer40k': {
        '社会结构': {'社会阶层': -10, '政治稳定': -8, '势力密度': -9, '法治程度': -5, '教育水平': -8, '家庭观念': -6},
        '自然环境': {'灾害频率': 9, '气候适宜': -8, '地形多样': 5, '资源丰富': -7},
        '经济体系': {'经济自由': -9, '科技水平': -3, '资源分配': -9, '贸易开放': 1},
        '超自然': {'超自然强度': 10, '普及程度': 8, '危险程度': 10, '可控程度': -8},
        '人口构成': {'种族多样': -7, '人口密度': 8, '语言统一': -5, '文化多元': -6},
        '文化面貌': {'价值观对立': -8, '宗教信仰': 9, '艺术繁荣': 2, '传统保留': -7},
    },
    'blue_archive_abydos': {
        '社会结构': {'社会阶层': 3, '政治稳定': -6, '势力密度': 5, '法治程度': 4, '教育水平': 7, '家庭观念': 5},
        '自然环境': {'灾害频率': 4, '气候适宜': -5, '地形多样': 3, '资源丰富': -6},
        '经济体系': {'经济自由': 5, '科技水平': 6, '资源分配': -4, '贸易开放': 5},
        '超自然': {'超自然强度': 0, '普及程度': 0, '危险程度': 0, '可控程度': 0},
        '人口构成': {'种族多样': 2, '人口密度': -4, '语言统一': 8, '文化多元': 4},
        '文化面貌': {'价值观对立': 2, '宗教信仰': 1, '艺术繁荣': 6, '传统保留': 3},
    },
    'blue_archive_gamedev': {
        '社会结构': {'社会阶层': 2, '政治稳定': -4, '势力密度': 4, '法治程度': 5, '教育水平': 8, '家庭观念': 4},
        '自然环境': {'灾害频率': 1, '气候适宜': 6, '地形多样': 2, '资源丰富': 6},
        '经济体系': {'经济自由': 6, '科技水平': 9, '资源分配': 1, '贸易开放': 7},
        '超自然': {'超自然强度': 0, '普及程度': 0, '危险程度': 0, '可控程度': 0},
        '人口构成': {'种族多样': 2, '人口密度': 6, '语言统一': 8, '文化多元': 5},
        '文化面貌': {'价值观对立': 1, '宗教信仰': 1, '艺术繁荣': 8, '传统保留': 2},
    },
}

def _merge_world_tag_changes(game_tags, changes):
    """将 LLM 返回的世界书变化量（加减值）累加到 game_tags。
    支持三种格式：
      1. 点号扁平格式: {'社会结构.社会阶层': 2, '自然环境.灾害频率': -3}
      2. 嵌套格式:     {'社会结构': {'社会阶层': 2}, '自然环境': {'灾害频率': -3}}
      3. 简单标量格式: {'新分类名': 5}（自动转为嵌套格式处理，新分类下创建'新标签'键）
    值是变化量（delta），会累加到现有值上（无上下限）。
    新增的分类和标签会自动创建。
    """
    for key, val in changes.items():
        if isinstance(val, dict):
            # 格式2：嵌套格式
            cat = key
            if cat not in game_tags:
                game_tags[cat] = {}
            if not isinstance(game_tags[cat], dict):
                continue
            for tag, v in val.items():
                try:
                    delta = int(v)
                    old = game_tags[cat].get(tag, 0)
                    if isinstance(old, (int, float)):
                        game_tags[cat][tag] = old + delta
                    else:
                        game_tags[cat][tag] = delta
                except (ValueError, TypeError):
                    pass
        elif '.' in key and isinstance(val, (int, float, str)):
            # 格式1：点号扁平格式
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
        elif isinstance(val, (int, float)):
            # 格式3：简单标量格式 - 整个分类被赋予一个总值
            # 自动转换为嵌套格式：创建该分类，并在总值标签下记录
            cat = key
            if cat not in game_tags:
                game_tags[cat] = {}
            if not isinstance(game_tags[cat], dict):
                continue
            # 在分类下创建"总值"标签
            try:
                delta = int(val)
                old = game_tags[cat].get('总值', 0)
                if isinstance(old, (int, float)):
                    game_tags[cat]['总值'] = old + delta
                else:
                    game_tags[cat]['总值'] = delta
            except (ValueError, TypeError):
                pass


def format_world_tags(tags):
    """格式化世界书标签，支持预定义分类和新添加的分类"""
    if not tags:
        return ''
    # 预定义分类的显示顺序和标签
    predefined_labels = {
        '社会结构': '【社会结构】',
        '自然环境': '【自然环境】',
        '经济体系': '【经济体系】',
        '超自然': '【超自然】',
        '人口构成': '【人口构成】',
        '文化面貌': '【文化面貌】',
    }
    lines = ['\n=== 世界书 ===']
    # 先显示预定义分类
    for key, label in predefined_labels.items():
        cat = tags.get(key, {})
        if cat and isinstance(cat, dict):
            parts = [f'{k}: {v}' for k, v in cat.items()]
            lines.append(f'{label}  {" | ".join(parts)}')
    # 再显示新增的分类（不在预定义中的）
    for key, cat in tags.items():
        if key in predefined_labels:
            continue
        if cat and isinstance(cat, dict):
            label = f'【{key}】'
            parts = [f'{k}: {v}' for k, v in cat.items()]
            lines.append(f'{label}  {" | ".join(parts)}')
    return '\n'.join(lines)


def get_world_tags(world):
    wid = world.get('id', '')
    tags = WORLD_TAG_DEFAULTS.get(wid)
    if tags:
        return json.loads(json.dumps(tags))
    parent = world.get('parent')
    if parent and parent in WORLD_TAG_DEFAULTS:
        return json.loads(json.dumps(WORLD_TAG_DEFAULTS[parent]))
    return {}



# 天赋数据

TALENTS = [

    {

        'id': 'born_rich',

        'name': '豪门之子',

        'description': '出生在富甲一方的家族',

        'rarity': 'rare',

        'effect': {'家境': 4},

        'color': '#6366f1'

    },

    {

        'id': 'beauty',

        'name': '绝世美颜',

        'description': '容貌惊人，令人过目不忘',

        'rarity': 'rare',

        'effect': {'容貌': 4},

        'color': '#6366f1'

    },

    {

        'id': 'genius',

        'name': '天纵奇才',

        'description': '智力超群，学什么都特别快',

        'rarity': 'epic',

        'effect': {'智力': 5},

        'color': '#9333ea'

    },

    {

        'id': 'invincible',

        'name': '金刚不坏',

        'description': '天生体魄堪称完美，打不烂摔不坏',

        'rarity': 'epic',

        'effect': {'体质': 5},

        'color': '#9333ea'

    },

    {

        'id': 'lucky',

        'name': '幸运儿',

        'description': '运气特别好，总能逢凶化吉',

        'rarity': 'rare',

        'effect': {},

        'color': '#6366f1'

    },

    {

        'id': 'bookworm',

        'name': '书虫',

        'description': '从小就喜欢读书，知识渊博',

        'rarity': 'common',

        'effect': {'智力': 2},

        'color': '#6b7280'

    },

    {

        'id': 'athlete',

        'name': '运动健将',

        'description': '体育方面特别有天赋',

        'rarity': 'common',

        'effect': {'体质': 2},

        'color': '#6b7280'

    },

    {

        'id': 'sociable',

        'name': '社交达人',

        'description': '人缘特别好，朋友遍布天下',

        'rarity': 'common',

        'effect': {},

        'color': '#6b7280'

    },

    {

        'id': 'hardworking',

        'name': '勤奋刻苦',

        'description': '比普通人更能吃苦',

        'rarity': 'common',

        'effect': {},

        'color': '#6b7280'

    },

    {

        'id': 'artistic',

        'name': '艺术细胞',

        'description': '在艺术方面有特别的天赋',

        'rarity': 'rare',

        'effect': {},

        'color': '#6366f1'

    },

    {

        'id': 'destructive',

        'name': '天生破坏王',

        'description': '碰什么坏什么，电子产品见了你都瑟瑟发抖',

        'rarity': 'common',

        'effect': {},

        'color': '#6b7280',

        'negative': True

    },

    {

        'id': 'slow_witted',

        'name': '天生愚钝',

        'description': '反应比普通人慢半拍',

        'rarity': 'common',

        'effect': {'智力': -2},

        'color': '#6b7280',

        'negative': True

    },

    {

        'id': 'weak_sickly',

        'name': '体弱多病',

        'description': '从小就容易生病',

        'rarity': 'common',

        'effect': {'体质': -2},

        'color': '#6b7280',

        'negative': True

    },

    {

        'id': 'poor_family',

        'name': '家徒四壁',

        'description': '出生在一个非常贫困的家庭',

        'rarity': 'rare',

        'effect': {'家境': -3},

        'color': '#6366f1',

        'negative': True

    },

    {

        'id': 'average',

        'name': '平平无奇',

        'description': '没有什么特别的，但也没有什么缺点',

        'rarity': 'common',

        'effect': {},

        'color': '#6b7280'

    },

    {

        'id': 'rebirth',

        'name': '重生者',

        'description': '带着前世的记忆重开',

        'rarity': 'legendary',

        'effect': {'智力': 3},

        'color': '#f59e0b'

    },

    {

        'id': 'system',

        'name': '随身系统',

        'description': '脑子里有个神秘系统',

        'rarity': 'legendary',

        'effect': {},

        'color': '#f59e0b'

    },

]



# 命运底色（已移除预设，改为自定义输入）

DESTINY_THEMES = []



# 性别选项

GENDERS = [

    {'id': 'male', 'name': '男性', 'icon': '👱'},

    {'id': 'female', 'name': '女性', 'icon': '👧'},

    {'id': 'other', 'name': '更多', 'icon': '✨'},

]



# 种族选项

RACES = [

    {'id': 'human', 'name': '人类', 'icon': '👤', 'unlocked': True, 'desc': '平凡但充满可能性', 'effect': '所有属性+1'},

    {'id': 'reincarnator', 'name': '穿越者', 'icon': '🌀', 'unlocked': True, 'desc': '带着异世界记忆转生', 'effect': '智力+2'},

    {'id': 'immortal', 'name': '长生种', 'icon': '⏳', 'unlocked': True, 'desc': '寿命悠久的古老种族', 'effect': '寿命延长'},

    {'id': 'magical_girl', 'name': '魔法少女', 'icon': '🌸', 'unlocked': True, 'desc': '契约之力，变身作战', 'effect': '魅力+2，运气+1'},

    {'id': 'demi_god', 'name': '半神', 'icon': '🌟', 'unlocked': True, 'desc': '身负神之血脉', 'effect': '所有属性+2'},

]



# 世界设定数据

WORLDS = [
    {
        'id': 'warhammer40k',
        'icon': '🗡',
        'name': '战锤40K',
        'description': '巢都底层崛起，在黑暗未来中为生存而战',
        'color': '#8b0000',
        'unlocked': True,
        'traits': ['力量', '意志', '智慧', '运气'],
        'trait_max': 10,
        'trait_total': 12,
        'use_llm': True,
        'preview': '第41千年。你出生在巢都最底层的贫民窟，在污染和犯罪中挣扎求生。帝国、混沌、异形……在这黑暗的宇宙中，只有战争永恒。',
        'prompt': '你是一个黑暗科幻小说的叙事者。背景是战锤40K的世界——人类帝国统治银河系，但永恒的战火从未停息。你出生在一颗巢都世界最底层的贫民窟，在污染、犯罪和邪教的包围中挣扎求生。帝国卫队、星际战士、混沌势力、欧克兽人……各种威胁无处不在。在这黑暗的第41千年，只有战争永恒。',
        'events': [],
    },

    {

        'id': 'blue_archive',

        'icon': '📚',

        'name': '蔚蓝档案',

        'description': '扮演老师，拯救学生',

        'color': '#1e90ff',

        'unlocked': True,

        'chapter_select': True,

        'traits': ['勇气', '谋略', '战力', '体质'],

        'trait_max': 10,

        'trait_total': 12,

        'use_llm': True,

        'prompt': '',

        'events': [],

    },

    {

        'id': 'blue_archive_abydos',

        'icon': '🏫',

        'name': '阿拜多斯篇',

        'description': '即将废校的阿拜多斯高中，你能挽救它吗？',

        'color': '#f59e0b',

        'unlocked': True,

        'hidden': True,

        'parent': 'blue_archive',

        'traits': ['勇气', '谋略', '战力', '体质'],

        'trait_max': 10,

        'trait_total': 12,

        'use_llm': True,

        'time_unit': '周',

        'ending_type': 'mission',

        'preview': '你是夏莱的老师，来到濒临废校的阿拜多斯高中。五个学生背负着巨额债务，在这所风沙中的学校里，你能否成为她们依靠的大人？',
        'prompt': '你是一个基于《蔚蓝档案》世界观的故事生成器。世界观设定：舞台是基沃托斯由数千个拥有自治权的学园组成的巨型学园都市。联邦学生会因会长失踪陷入瘫痪。核心舞台是阿拜多斯自治区，阿拜多斯高中曾是名校，但因债务陷入绝境，背负9亿多元债务，仅剩五名学生在籍。你是老师（Sensei），隶属于夏莱联邦搜查部，拥有战略指挥能力。核心冲突是对策委员会与凯撒集团的对抗、债务危机以及领土下的秘密。配角：砂狼白子、小鸟游星野、奥空绫音、黑见芹香、十六夜野宫。叙事用第二人称「你」展开，重视角色对话与情感羁绊。每个事件附带属性变化trait_changes（勇气/谋略/战力/体质），范围-2到+2。关键设定：finished字段用"success"或"fail"。success条件：打倒凯撒PMC或还清债务。fail条件：关键学生死亡。玩家主动放弃或选择高危选项时直接fail。角色意志低落可以缓一缓，给机会翻盘。玩家自定义输入享有最高优先级，写了什么就发生什么，不得弱化。当finished为success或fail时，最后一个事件必须是明确的结局，不能留悬念。epitaph写任务总结。注意：当finished为success或fail时，最后一个事件必须是明确的结局描述，不能留悬念或问号。',

        'events': [],

    },

    {

        'id': 'blue_archive_gamedev',

        'icon': '🎮',

        'name': '游戏开发部篇',

        'description': '拯救废部的游戏开发部，做出最好的游戏！',

        'color': '#e040fb',

        'unlocked': True,

        'hidden': True,

        'parent': 'blue_archive',

        'traits': ['勇气', '谋略', '战力', '体质'],

        'trait_max': 10,

        'trait_total': 12,

        'use_llm': True,

        'time_unit': '周',

        'ending_type': 'mission',

        'preview': '你是夏莱的老师，来到了千年科技学院的游戏开发部。几个热爱游戏却面临废部的少女，能否在社团大赛上创造奇迹？',
        'prompt': '你是一个基于《蔚蓝档案》世界观的故事生成器。世界观设定：舞台是基沃托斯由数千个学园组成的巨型学园都市。核心舞台是千年科技学院，故事聚焦于游戏开发部。困境是游戏开发部面临废部，开发的游戏被评为年度最烂第一名，唯一生路是在社团大赛上获奖。你是夏莱的老师（Sensei），担任游戏制作顾问。配角：花冈柚子、才羽桃井、才羽绿、天童爱丽丝。叙事用第一人称「我」展开，节奏轻快，允许游戏术语梗。每个事件附带属性变化trait_changes（勇气/谋略/战力/体质），范围-2到+2。关键设定：finished字段用"success"或"fail"。success条件：帮助游戏开发部免于解散并让天童爱丽丝被世人接受。fail条件：无可见。玩家主动放弃或选择高危选项时直接fail。角色意志低落可以缓一缓，给机会翻盘。玩家自定义输入享有最高优先级，写了什么就发生什么，不得弱化。当finished为success或fail时，最后一个事件必须是明确的结局，不能留悬念。epitaph写任务总结。注意：当finished为success或fail时，最后一个事件必须是明确的结局描述，不能留悬念或问号。',

        'events': [],

    },

    {

        'id': 'arknights',

        'icon': '🧬',

        'name': '明日方舟',

        'description': '源石感染、天灾横行，在废墟中为生存而战',

        'color': '#1a1a2e',

        'unlocked': True,

        'traits': ['战斗', '源石技艺', '战术', '意志'],

        'trait_max': 10,

        'trait_total': 12,

        'use_llm': True,

        'preview': '源石病肆虐，感染者与非感染者的矛盾日益激化。你身处一个充满危机与抉择的世界，每个人都要为自己的信念而战。',
        'prompt': '你是一个末世科幻小说的叙事者。背景是《明日方舟》的世界——源石污染大地，感染者和非感染者之间的冲突日益激烈，天灾频繁降临。罗德岛制药公司在混乱中寻求治愈之道，而整合运动则以暴力反抗压迫。在这片充满矿石病、源石技艺和派系斗争的大地上，每个人都要为自己的信念而战。',

        'events': [],

    },

    {

        'id': 'harry_potter',

        'icon': '⚡',

        'name': '魔法世界',

        'description': '踏入魔法世界，度过你的巫师一生',

        'color': '#7f5af0',

        'unlocked': True,

        'traits': ['魔力', '智慧', '勇气', '运气'],

        'trait_max': 10,

        'trait_total': 12,

        'use_llm': True,

        'preview': '你收到了魔法学校的来信。穿过迷雾中的站台，踏入这个充满咒语、神奇动物与隐秘阴谋的世界。你的一生将如何展开？',

        'prompt': '你是一个魔法世界叙事者。背景设定在类似《哈利波特》的魔法世界——存在巫师社会、魔法学校（四大学院）、魔法部、黑巫师势力。魔法通过魔杖和咒语施展，存在神奇动物、飞行球赛、魔法物品。主角从童年开始完整一生：童年（0-10岁）→魔法学校（11-17岁，共7学年）→毕业后成年生活（工作、冒险、婚姻家庭）→中年→老年。叙事按年度展开，用第二人称「你」描写完整人生历程。早期围绕校园学习、友情、冒险；后期进入魔法部等工作、对抗黑巫师。每个事件附带属性变化trait_changes（魔力/智慧/勇气/运气），范围-2到+2。重要：不要随意安排主角死亡，故事应自然展开，像普通人一样经历生老病死，寿命与人类正常相当（70-100岁）。角色可以受伤、失败、经历低谷，但不会英年早逝。finished字段取值——"true"=正常寿命结束/故事自然落幕，"success"=击败黑魔王/成为传奇巫师等重大成就，"fail"=仅当玩家主动选择死亡/被黑魔法吞噬时。玩家自定义输入享有最高优先级。当finished不为false时，最后一个事件必须是明确的结局。',

        'events': []

    },

    {

        'id': 'wuxia',

        'icon': '⚔️',

        'name': '武侠江湖',

        'description': '刀光剑影的江湖世界，书写你的侠客传奇',

        'color': '#c0392b',

        'unlocked': True,

        'traits': ['内力', '身法', '悟性', '侠义'],

        'trait_max': 10,

        'trait_total': 12,

        'use_llm': True,

        'preview': '你踏入了一个刀光剑影的江湖。这里有正道魔道之分，有武林秘籍的诱惑，也有快意恩仇的豪情。你将成为怎样的侠客？',

        'prompt': '你是一个武侠小说叙事者。背景设定在古典中国风的武侠江湖世界——存在正派（少林、武当、峨眉等）、魔教、朝廷六扇门。武者通过修炼内力、学习招式修练武艺。有武林秘籍、江湖恩怨、门派纷争、武林大会等元素。叙事按年度展开，用第二人称「你」描写主角的江湖一生。早期习武练功、行走江湖；中期扬名立万、门派争斗；后期归隐或成为一代宗师。每个事件附带属性变化trait_changes（内力/身法/悟性/侠义），范围-2到+2。重要：角色可以受伤失败，但不会随意死亡。寿命与人类正常相当。finished字段取值——"true"=正常寿命结束/归隐江湖，"success"=成为一代宗师/击败魔教等重大成就，"fail"=仅当玩家主动选择死亡/走火入魔时。玩家自定义输入享有最高优先级。当finished不为false时，最后一个事件必须是明确的结局。',

        'events': []

    },

    {

        'id': 'wasteland',

        'icon': '☢️',

        'name': '末日废土',

        'description': '核战后的荒芜大地，在辐射中求生重建',

        'color': '#78716c',

        'unlocked': True,

        'traits': ['体质', '感知', '意志', '魅力'],

        'trait_max': 10,

        'trait_total': 12,

        'use_llm': True,

        'preview': '核战过后，文明已成废墟。辐射尘雾弥漫，变异兽横行，幸存者在据点中艰难求生。在这片废土上，你将如何活下去？',

        'prompt': '你是一个末日废土叙事者。背景设定在核战争后的废土世界——文明崩溃，辐射污染严重，变异的动植物威胁着幸存者的生存。存在拾荒者部落、军阀控制的城市、废土游商、地下避难所等组织形式。资源稀缺、水源污染、辐射风暴频发。叙事按年度展开，用第二人称「你」描述在废土中求生的故事。早期挣扎求生、寻找资源；中期建立势力、与其他团体交涉；后期探索旧世界遗迹、尝试重建文明。每个事件附带属性变化trait_changes（体质/感知/意志/魅力），范围-2到+2。重要：角色可以受伤、感染辐射、遭受背叛，但不会英年早逝。故事应自然展开，角色可能因玩家选择而死亡，但不会无故暴毙。finished字段取值——"true"=自然死亡/在废土中安然离世，"success"=找到新家园/重建文明等重大成就，"fail"=死亡（玩家主动选择或剧情走向）。玩家自定义输入享有最高优先级。当finished不为false时，最后一个事件必须是明确的结局。',

        'events': []

    }

]









class LLMClient:

    """OpenAI 格式的 LLM 客户端"""



    def __init__(self, config):

        self.config = config

        self.enabled = config['enabled'] and config['api_key'] and HAS_REQUESTS

        self.custom_body = config.get('custom_request_body', {})



    def _make_request(self, messages, override=None):

        """发送请求到 LLM API。启用自定义时只用自定义参数；否则只用全局 config。"""

        if override and override.get('enabled'):
            cfg = override
            url = f"{cfg.get('api_base', '').rstrip('/')}/chat/completions"
            body = cfg.get('custom_request_body', {})
        else:
            cfg = self.config
            url = f"{cfg['api_base'].rstrip('/')}/chat/completions"
            body = self.custom_body

        request_body = {
            'model': cfg.get('model', ''),
            'messages': messages,
            'temperature': float(cfg.get('temperature', 0.9)),
            'max_tokens': max(int(cfg.get('max_tokens', 8192)), 2048),
        }

        if cfg.get('top_p') is not None:
            body = {**body, 'top_p': float(cfg['top_p'])}
        if body:
            request_body.update(body)

        return requests.post(
            url,
            headers={
                'Authorization': f"Bearer {cfg.get('api_key', '')}",
                'Content-Type': 'application/json',
            },
            json=request_body,
            timeout=60
        )



    def generate_events_batch(self, world, game_state, override=None):

        """使用 LLM 生成批量人生事件 + 一个选择点，返回JSON格式"""

        # 只要全局启用 或 自定义启用了，就允许调用
        if not self.enabled and not (override and override.get('enabled')):

            return None



        try:

            traits = game_state.get('traits', {})

            current_year = game_state.get('current_year', 0)

            time_unit = world.get('time_unit', '岁')

            history = game_state.get('history', [])

            talents = game_state.get('talents', [])

            background = game_state.get('background', '')



            trait_text = '，'.join([f'{k}: {v}' for k, v in traits.items()])

            batch_min = (override or {}).get('batch_min', self.config.get('batch_min', 1))

            batch_max = (override or {}).get('batch_max', self.config.get('batch_max', 3))

            batch_size = random.randint(batch_min, batch_max)

            world_traits = world.get('traits', ['容貌', '智力', '体质', '家境'])

            tc_example = ', '.join([f'\"{t}\": 0' for t in world_traits])

            talent_text = ''

            if talents:

                talent_parts = []

                for t in talents:

                    effects = t.get('effect', {})

                    if effects:

                        eff_str = '，'.join([f'{k}+{v}' for k, v in effects.items()])

                        talent_parts.append(f'{t["name"]}({eff_str})')

                    else:

                        talent_parts.append(t['name'])

                talent_text = '，'.join(talent_parts)

            else:

                talent_text = '无'



            race = game_state.get('race', {})

            custom_race = game_state.get('custom_race', '')

            custom_race_desc = game_state.get('custom_race_desc', '')

            race_text = ''

            if custom_race:

                race_text = f'自定义种族：{custom_race}'

                if custom_race_desc:

                    race_text += f'（{custom_race_desc}）'

            elif race:

                race_name = race.get('name', '未知')

                race_desc = race.get('desc', '')

                race_effect = race.get('effect', '')

                race_text = f'种族：{race_name}'

                if race_desc:

                    race_text += f'（{race_desc}）'

                if race_effect:

                    race_text += f'，种族特性：{race_effect}'



            history_text = ''

            if background:

                history_text += f'身世：{background}\n\n'



            if history:

                history_text += '人生历程：\n'

                for idx, record in enumerate(history, 1):

                    history_text += f"{record.get('year', idx)}{world.get('time_unit', '岁')}：{record.get('event', '')}\n"

                    if record.get('choice'):

                        history_text += f"  选择：{record.get('choice')}\n"

                    history_text += '\n'



            world_tags = game_state.get('world_tags') or get_world_tags(world)
            tags_text = format_world_tags(world_tags)
            # 字数范围 & 文风
            event_words = (override or {}).get('event_words') or self.config.get('event_words', '50-150')
            writing_style = (override or {}).get('writing_style') or self.config.get('writing_style', '')
            style_map = {
                '史诗': '具有史诗感，宏大叙事，气势磅礴',
                '俏皮': '轻松幽默，古灵精怪，带点调侃',
                '细腻': '情感丰富，心理描写入微，语言优美',
            }
            style_desc = style_map.get(writing_style, '简洁明了')
            system_prompt = f"""{world.get('prompt', '你是一个人生模拟游戏的叙事者。')}
{tags_text}



核心规则：

1. 每次生成 {batch_size} 年的连续年度事件，每个事件的year不一定唯一，可以重复

2. 每个事件{event_words}字，语言{style_desc}

3. 所有事件用第二人称「你」（如：你出生了、你上学了）

4. finished为false时最后一年的事件必须是人生转折点或冲突点

5. 基于最后一年的事件生成 3 个选择



6. 最重要规则——你必须严格参考「上次选择」，让选择产生合理后果：

   - 玩家在自定义输入框里写的内容享有最高优先级，必须不折不扣地执行。
     如果用户写了「自杀」「奇迹」「毁灭」等极端内容，直接按字面执行，不得弱化或美化。
   - 如果用户选了「自杀」「赴死」「牺牲」「放手」「放弃生命」等自我毁灭选项
     本批第一个事件就是死亡场景，finished设为"true"，游戏结束。
   - 如果用户选了高风险选项 → 承担后果（受伤、入狱、死亡等）。
   - 如果用户选了正面选项 → 剧情向其所希望方向发展。



7. 风格与世界设定保持一致

8. 结合玩家天赋和属性融入叙事

9. 事件符合玩家年龄

10. 前后事件不能矛盾，必须高度一致

11. 世界书影响剧情（重要！）：上面「=== 世界书 ===」中每个标签的数值
    代表当前世界的状态（数值越高越正面/强大，越低越负面/薄弱）。
    你必须让生成的事件与这些数值一致：
    - 正面值高的领域 → 事件中体现其优势（如科技水平高→出现高科技场景）
    - 负面的领域 → 事件中体现其困境（如政治稳定低→出现动乱、阴谋）
    - 数值已远离0（绝对值很大）→ 该领域在事件中占据突出地位
    - 数值变化时 → 剧情应反映这种变化（如灾害频率增加→天灾降临）

12. 每个选择附带后果描述（consequence），用一句话说明该选择可能导致的后果

13. 世界书标签变化（必须执行！）：根据本批事件对世界造成的影响，用变化量（加减值）更新世界标签。
	   格式为嵌套JSON，key是分类名，value是该分类下被影响的标签及其变化量（正=改善，负=恶化）。
	   只列出有变化的标签。不要写绝对值，写变化量！
	   示例1——战争导致社会阶层+2、政治稳定-3：
	   "world_tag_changes": {{"社会结构": {{"社会阶层": 2, "政治稳定": -3}}}}
	   示例2——科技进步带来科技水平+1：
	   "world_tag_changes": {{"经济体系": {{"科技水平": 1}}}}
	   示例3——没有影响世界的变化则留空：
	   "world_tag_changes": {{}}







JSON格式（严格遵守）：

{{

  "events": [

    {{"year": {current_year + 1}, "text": "事件描述", "trait_changes": {{{tc_example}}}}},

    {{"year": {current_year + 2}, "text": "事件描述", "trait_changes": {{{tc_example}}}}},

    ...

  ],

  "choices": [

    {{"text": "选择A", "mood": "positive/negative/neutral", "consequence": "可能的后果描述"}},

    {{"text": "选择B", "mood": "positive/negative/neutral", "consequence": "可能的后果"}},

    {{"text": "选择C", "mood": "positive/negative/neutral", "consequence": "可能的后果"}}

  ],
  "world_tag_changes": {{"分类名": {{"标签名": 变化量}}}} 或 {{}},
  "finished": "false",

  "fortune": 50,
  "epitaph": "若finished不为false则写任务总结/墓志铭"

}}



finished字段取值说明：
- 普通世界（岁单位）："true" = 故事结束（寿命终了/剧情终点），"false" = 继续
重要：不要回避失败结局。如果玩家选择了高风险选项或剧情走向失败条件，请大胆给出"fail"结局。
- 注意：当finished不为false时，最后一个事件必须是明确的结局描述，不能留悬念或问号。
失败和成功的结局同样有故事价值。玩家自定义输入享有最高优先级，写了什么就发生什么，不得弱化。


14. 运势值（fortune）：每个批次输出一个运势值（0-100），表示当前主角的气运高低。受之前的选择、事件和属性影响。高运势（70+）意味着好运连连；低运势（30以下）意味着霉运当头。

注意：

- events中同年可以有多个事件，前端会合并显示

- 返回纯粹JSON，不要其他文字

- events数组长度 {batch_size}

- fortune 为整数，范围 0-100

"""



            custom_destiny = game_state.get('custom_destiny', '')

            user_prompt = f"""世界设定：{world['name']}

{race_text}

玩家天赋（含属性加成）：{talent_text}

玩家最终属性：{trait_text}

当前进度：{current_year} {time_unit}
"""

            if custom_destiny:
                user_prompt += f'\n玩家期望的命运底色：{custom_destiny}\n'

            user_prompt += f"""
=== 完整人生历史（必须严格参考，不能矛盾） ===

{history_text}

==========



请基于以上所有历史，生成接下来 {batch_size} 年的人生事件和最终的选择。

特别注意：用户的自定义输入必须不折不扣执行；如果用户选了自杀/赴死等自我毁灭选项，本批必须让角色死亡。"""



            messages = [

                {'role': 'system', 'content': system_prompt},

                {'role': 'user', 'content': user_prompt}

            ]



            max_retries = self.config.get('max_retries', 1)
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    response = self._make_request(messages, override)

                    if response.status_code == 200:
                        result = response.json()
                        resp_content = result['choices'][0]['message']['content'].strip()
                        # 移除 markdown 代码块包裹
                        if '```' in resp_content:
                            resp_content = resp_content.replace('```json', '').replace('```', '').strip()
                        try:
                            return json.loads(resp_content)
                        except:
                            try:
                                json_start = resp_content.find('{')
                                json_end = resp_content.rfind('}') + 1
                                if json_start >= 0 and json_end > json_start:
                                    json_str = resp_content[json_start:json_end]
                                    return json.loads(json_str)
                            except:
                                pass
                        last_error = f"JSON解析失败 (前500字): {resp_content[:500]}"
                        print(f"[LLM] {last_error}")
                        if attempt < max_retries:
                            print(f"[LLM] 重试 {attempt+1}/{max_retries}...")
                            continue
                    else:
                        err_msg = response.text[:200] if response.text else '无响应'
                        last_error = f"API错误 {response.status_code}: {err_msg}"
                        print(f"[LLM] {last_error}")
                        if attempt < max_retries:
                            print(f"[LLM] 重试 {attempt+1}/{max_retries}...")
                            continue
                except Exception as e:
                    last_error = str(e)
                    print(f"[LLM] 调用异常: {e}")
                    if attempt < max_retries:
                        print(f"[LLM] 重试 {attempt+1}/{max_retries}...")
                        continue
                break
            return None

        except Exception as e:
            print(f"[LLM] 调用异常: {e}")
            return None


    def generate_background(self, world, game_state, override=None):

        """生成身世介绍"""

        if not self.enabled and not (override and override.get('enabled')):

            return None



        try:

            traits = game_state.get('traits', {})

            talents = game_state.get('talents', [])

            gender = game_state.get('gender', {}).get('name', '未知')

            race = game_state.get('race', {}).get('name', '未知')

            player_name = game_state.get('player_name', '')

            trait_text = '，'.join([f'{k}: {v}' for k, v in traits.items()])



            talent_text = ''

            if talents:

                talent_parts = []

                for t in talents:

                    effects = t.get('effect', {})

                    if effects:

                        eff_str = '，'.join([f'{k}+{v}' for k, v in effects.items()])

                        talent_parts.append(f'{t["name"]}({eff_str})')

                    else:

                        talent_parts.append(t['name'])

                talent_text = '，'.join(talent_parts)

            else:

                talent_text = '无'



            system_prompt = """你是一个人生模拟游戏的叙事者。

根据玩家的天赋、属性和世界设定，生成一段身世介绍（150字左右）和该世界的初始世界书标签。

世界书标签规则：
- 标签自由分类，不必拘泥于固定维度，根据世界特色自行创建
- 每个分类下若干标签，标签取值范围 -10（极度负面）到 +10（极度正面），0 为中性
- 标签应反映世界核心特征：如魔法世界的「魔力浓度」、废土世界的「辐射等级」、星际文明的「外星威胁」等
- 分类和标签数量不限，但总标签数建议在 8-15 个

要求：
- 身世要具有叙事感，像小说开头，结合天赋、属性和玩家期望的命运底色
- 始终用第二人称「你」称呼主角，不要用主角名替代「你」
- 世界书标签要准确反映世界特色，与描述高度一致
- 以JSON格式返回：{"background": "身世介绍", "world_tags": {"分类名": {"标签名": 数值}}}

"""



            custom_destiny = game_state.get('custom_destiny', '')

            user_prompt = f"""世界设定：{world['name']} — {world.get('description', '')}

性别：{gender}

种族：{race}

天赋：{talent_text}

属性：{trait_text}
{f'期望的命运底色：{custom_destiny}' if custom_destiny else ''}
{f'主角名：{player_name}' if player_name else ''}

请生成身世介绍和世界书标签："""



            messages = [

                {'role': 'system', 'content': system_prompt},

                {'role': 'user', 'content': user_prompt}

            ]



            response = self._make_request(messages, override)



            if response.status_code == 200:

                result = response.json()

                content = result['choices'][0]['message']['content'].strip()

                try:

                    json_result = json.loads(content)

                    return json_result
                except:

                    try:

                        json_start = content.find('{')

                        json_end = content.rfind('}') + 1

                        if json_start >= 0 and json_end > json_start:

                            json_str = content[json_start:json_end]

                            json_result = json.loads(json_str)

                            return json_result

                    except:

                        pass

                # JSON 解析失败时，把原始内容当 background 返回

                return {'background': content, 'world_tags': {}}

            else:

                return None



        except Exception as e:

            print(f"LLM background error: {e}")

            return None



    def generate_ending_evaluation(self, world, game_state, override=None):

        """生成人生总结评分"""

        enabled = override.get('enabled', self.enabled) if override else self.enabled

        if not enabled:

            return None



        try:

            traits = game_state.get('traits', {})
            time_unit = world.get('time_unit', '岁')

            talents = game_state.get('talents', [])

            history = game_state.get('history', [])

            background = game_state.get('background', '')

            race = game_state.get('race', {}).get('name', '未知')

            gender = game_state.get('gender', {}).get('name', '未知')



            trait_text = '，'.join([f'{k}: {v}' for k, v in traits.items()])



            talent_text = '，'.join([t['name'] for t in talents]) if talents else '无'



            history_text = ''

            if background:

                history_text += f'身世：{background}\n\n'

            for record in history:

                history_text += f"{record.get('year', '?')}{world.get('time_unit', '岁')}：{record.get('event', '')}"

                if record.get('choice'):

                    history_text += f" → {record['choice']}"

                history_text += '\n'



            system_prompt = """你是一个人生评价者。请根据玩家的一生经历，给出客观评分和总结。



以JSON格式返回：

{

  "score": 85,

  "summary": "一生总结（50字内）",

  "epitaph": "墓志铭（20字内）",

  "title": "结局标题（如：圆满人生、壮志未酬等）",

  "type": "good/normal/bad"

}



评分规则（score 0-100）：

- 寿命长短（长寿加分）

- 经历丰富度

- 选择质量

- 综合命运



type取值：good=好结局, normal=普通结局, bad=坏结局"""



            user_prompt = f"""世界设定：{world.get('name', '未知')}

性别：{gender}

种族：{race}

天赋：{talent_text}

属性：{trait_text}



=== 完整人生经历 ===

{history_text}

==================



请评价这一生："""



            messages = [

                {'role': 'system', 'content': system_prompt},

                {'role': 'user', 'content': user_prompt}

            ]



            response = self._make_request(messages, override)



            if response.status_code == 200:

                result = response.json()

                content = result['choices'][0]['message']['content'].strip()

                try:

                    return json.loads(content)

                except:

                    try:

                        json_start = content.find('{')

                        json_end = content.rfind('}') + 1

                        if json_start >= 0 and json_end > json_start:

                            return json.loads(content[json_start:json_end])

                    except:

                        pass

                return None

            else:

                return None



        except Exception as e:

            print(f"LLM ending error: {e}")

            return None





# 初始化 LLM 客户端

llm_client = LLMClient(LLM_CONFIG)





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

    if not session.get('entry_origin'):

        return False

    return True





@app.route('/')

def index():

    """首页 - 显示世界选择界面"""

    session['entry_origin'] = 'home'

    return render_template('index.html', worlds=WORLDS)





@app.route('/custom')

def custom_world():

    """自定义世界创建页面"""

    session['entry_origin'] = 'home'

    return render_template('custom.html')


@app.route('/world/random')
def random_world_detail():

    """展示 LLM 生成的随机世界"""

    world = session.get('custom_world')
    if not world:
        return render_template('error.html', message='请先生成随机世界 🎲', back_url='/'), 400

    session['entry_origin'] = 'home'

    # 随机世界使用自定义模板，不显示世界书（尚未生成）
    return render_template('world.html', world=world, world_tags=None, is_random=True)





@app.route('/world/<world_id>')

def world_detail(world_id):

    """世界详情页 - 开始游戏前的设定页"""

    session['entry_origin'] = 'home'

    if world_id == 'blue_archive':

        return render_template('blue_archive.html')

    if world_id == 'custom':

        return render_template('error.html',

            message='自定义世界请从首页创建 🌐',

            back_url='/'), 400

    world = get_world(world_id)

    if not world or not world['unlocked']:

        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404

    return render_template('world.html', world=world, world_tags=None)





@app.route('/api/random-world', methods=['POST'])

def api_random_world():

    """使用 LLM 生成一个随机世界"""

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

        # 随机世界使用更高的温度和 top_p 以增加创造性
        creative_override = dict(override) if override else {}
        creative_override['enabled'] = True
        creative_override['temperature'] = 1.2
        creative_override['top_p'] = 0.95

        response = llm_client._make_request(messages, creative_override)

        if response.status_code == 200:

            result = response.json()

            content = result['choices'][0]['message']['content'].strip()

            # 解析 JSON

            try:

                data = json.loads(content)

            except:

                json_start = content.find('{')

                json_end = content.rfind('}') + 1

                if json_start >= 0 and json_end > json_start:

                    data = json.loads(content[json_start:json_end])

                else:

                    return jsonify({'error': '生成失败，无法解析'}), 500

            # 构建世界对象，清理首尾空白
            world_name = str(data.get('name', '随机世界')).strip() or '随机世界'

            world = {

                'id': 'random',
                'icon': str(data.get('icon', '🌍')).strip() or '🌍',
                'name': world_name,
                'description': str(data.get('description', '一个神秘的世界')).strip(),
                'color': str(data.get('color', '#6366f1')).strip(),
                'unlocked': True,
                'traits': data.get('traits', ['力量', '智慧', '勇气', '运气']),
                'trait_max': 10,
                'trait_total': 12,
                'use_llm': True,
                'preview': str(data.get('preview', '')).strip(),
                'prompt': str(data.get('prompt', '')).strip(),
            }

            session['custom_world'] = world

            return jsonify({'status': 'ok', 'world': world})

        else:

            return jsonify({'error': f'API 错误: {response.status_code}'}), 500

    except Exception as e:

        return jsonify({'error': f'生成失败: {str(e)}'}), 500


@app.route('/game/custom/identity', methods=['GET', 'POST'])

def custom_game_identity():

    """自定义世界的身份设定"""

    if request.method == 'GET':

        name = request.args.get('name', '自定义世界')

        desc = request.args.get('desc', '你想象中的世界')

        raw_traits = request.args.get('traits', '')

        traits_list = [t.strip() for t in raw_traits.split(',') if t.strip()] if raw_traits else ['体质', '智力', '魅力', '运气']

        world = {

            'id': 'custom',

            'icon': '🌐',

            'name': name,

            'description': desc,

            'color': '#6366f1',

            'unlocked': True,

            'traits': traits_list,

            'trait_max': 10,

            'trait_total': 12,

            'use_llm': True,

            'prompt': f'你是一个小说叙事者。玩家在"{name}"世界开始了人生。世界观描述：{desc}。请根据这个设定生成符合世界观的人生事件。',

        }

        session['custom_world'] = world

        return render_template('identity.html', world=world,

                              genders=GENDERS, races=RACES, destinies=[])



    if request.method == 'POST':

        data = request.json

        game = session.get('game', {})

        custom_race = data.get('custom_race', '').strip()
        custom_race_desc = data.get('custom_race_desc', '').strip()

        race_obj = None

        if custom_race:

            race_obj = {'id': 'custom', 'name': custom_race, 'icon': '✨', 'unlocked': True}
            if custom_race_desc:
                race_obj['desc'] = custom_race_desc



        # 保留已有的 custom_world、world_name 等字段
        game.update({

            'world_id': game.get('world_id', 'custom'),

            'gender': next((g for g in GENDERS if g['id'] == data.get('gender')), GENDERS[0]),

            'race': race_obj or next((r for r in RACES if r['id'] == data.get('race')), RACES[0]),

            'custom_race': custom_race if custom_race else None,

            'custom_race_desc': custom_race_desc if custom_race_desc else None,

            'custom_destiny': data.get('custom_destiny', '').strip() or None,

            'step': 'identity_done'

        })

        session['game'] = game

        return jsonify({'status': 'ok', 'next_step': '/game/custom/talents'})

    return '', 405





@app.route('/game/<world_id>/quickstart', methods=['GET', 'POST'])

def game_quickstart(world_id):

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





@app.route('/game/<world_id>/start', methods=['POST'])

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

        'world_id': world_id,

        'gender': None,

        'race': None,

        'talents': None,

        'traits': None,

        'background': None,

        'step': 'not_started',

        'history': [],

        'player_name': pn,

        'show_record': show_record,

    }
    session['entry_origin'] = 'home'

    # 子世界（如蔚蓝档案）走快速通道，其余走标准身份设定
    next_step = '/game/' + world_id + '/quickstart' if world.get('parent') else '/game/' + world_id + '/identity'

    return jsonify({'status': 'ok', 'next_step': next_step})


@app.route('/game/random/start', methods=['POST'])
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
        'world_id': 'random',
        'world_name': world.get('name', '随机世界'),
        'custom_world': world,  # 保存完整世界数据，防止丢失
        'gender': None,
        'race': None,
        'talents': None,
        'traits': None,
        'background': None,
        'step': 'not_started',
        'history': [],
        'player_name': pn,
        'show_record': show_record,
    }
    session['entry_origin'] = 'home'

    return jsonify({'status': 'ok', 'next_step': '/game/custom/identity'})


@app.route('/game/<world_id>/identity', methods=['GET', 'POST'])

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

        # 保留已有的 player_name、show_record 等字段
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



    return render_template('identity.html', world=world,

                          genders=GENDERS, races=RACES, destinies=[])





@app.route('/game/<world_id>/talents', methods=['GET', 'POST'])

def game_talents(world_id):

    """天赋抽取页面"""

    world = get_world(world_id)

    if not world or not world['unlocked']:

        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404



    if 'game' not in session or not session['game'].get('gender'):

        return render_template('error.html',

            message='请先设定身份 🎭',

            back_url='/game/' + world_id + '/identity'), 400



    if request.method == 'POST':

        data = request.json

        if data.get('action') == 'draw':

            # 抽取天赋

            talents = draw_talents(3)

            session['game']['talent_pool'] = talents

            session['game']['rerolls_left'] = 3

            return jsonify({'talents': talents, 'rerolls_left': 3})

        elif data.get('action') == 'reroll':

            # 重新抽取

            rerolls_left = session['game'].get('rerolls_left', 0)

            if rerolls_left > 0:

                talents = draw_talents(3)

                session['game']['talent_pool'] = talents

                session['game']['rerolls_left'] = rerolls_left - 1

                return jsonify({'talents': talents, 'rerolls_left': rerolls_left - 1})

            return jsonify({'status': 'error', 'message': '没有重抽次数了'})

        elif data.get('action') == 'confirm':

            # 确认天赋

            talent_ids = data.get('talent_ids', [])

            talents = [t for t in session['game'].get('talent_pool', []) if t['id'] in talent_ids]

            session['game']['talents'] = talents

            session['game']['step'] = 'talents_done'

            return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/traits'})



    return render_template('talents.html', world=world)





@app.route('/game/<world_id>/traits', methods=['GET', 'POST'])

def game_traits(world_id):

    """属性分配页面"""

    world = get_world(world_id)

    if not world or not world['unlocked']:

        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404



    if session.get('game', {}).get('talents') is None:

        return render_template('error.html',

            message='请先抽取天赋 ✦',

            back_url='/game/' + world_id + '/talents'), 400



    if request.method == 'POST':

        data = request.json

        traits = data.get('traits', {})

        talents = session['game'].get('talents', [])

        traits = apply_talents_to_traits(traits, talents)

        session['game']['traits'] = traits

        session['game']['step'] = 'traits_done'

        return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/preview'})



    return render_template('traits.html', world=world,

                          talents=session['game'].get('talents', []))





@app.route('/game/<world_id>/preview', methods=['GET', 'POST'])

def game_preview(world_id):

    """命运预览页面"""

    world = get_world(world_id)

    if not world or not world['unlocked']:

        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404



    game = session.get('game', {})



    # 检查流程完整性

    if not game.get('traits') or game.get('talents') is None:

        return render_template('error.html',

            message='请先完成身份设定、天赋抽取和属性分配再来预览 ✨',

            back_url='/game/' + world_id + '/identity'), 400



    # 身世与世界书只用生成一次，存到session后复用

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
            if isinstance(bg_result, dict):
                background = bg_result.get('background', '')
                generated_tags = bg_result.get('world_tags')
            elif isinstance(bg_result, str):
                background = bg_result

        if not background:

            background = "你出生在一个普通的家庭，从小就表现出一些与众不同的特质。"

        session['game']['background'] = background
        # 保存 LLM 生成的世界标签（如果有）
        if generated_tags and isinstance(generated_tags, dict):
            session['game']['world_tags'] = generated_tags
            game['world_tags'] = generated_tags

    else:

        background = game['background']



    if request.method == 'POST':

        # player_name 和 show_record 已从世界详情页传入 session

        session['game']['current_year'] = 0

        session['game']['history'] = []
        # 优先用 LLM 生成的标签，没有则用硬编码默认
        if not game.get('world_tags'):
            wt = dict(get_world_tags(world)) if get_world_tags(world) else {}
            if wt:
                session['game']['world_tags'] = wt
        session['game']['step'] = 'playing'

        return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/play'})



    wt = game.get('world_tags') or get_world_tags(world)
    return render_template('preview.html', world=world, game=game, background=background, world_tags=wt)





@app.route('/game/<world_id>/play')

def game_play(world_id):

    """游戏主页面"""

    world = get_world(world_id)

    if not world or not world['unlocked']:

        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404



    if session.get('game', {}).get('step') != 'playing':

        return render_template('error.html',

            message='请先完成命运预览，再开始人生 🚀',

            back_url='/game/' + world_id + '/preview'), 400



    game = session.get('game', {})

    # 随机世界：确保 custom_world 被保存（防止丢失）
    if world_id == 'random' and not game.get('custom_world'):
        game['custom_world'] = world
        session['game'] = game

    wt = game.get('world_tags') or get_world_tags(world)
    return render_template('game.html', world=world, game=game, world_tags=wt)





@app.route('/game/<world_id>/next', methods=['POST'])

def game_next(world_id):

    """下一个事件 — LLM决定寿命，高年龄增加死亡概率"""

    world = get_world(world_id)

    if not world or not world['unlocked']:

        return jsonify({'error': '世界未解锁'}), 400



    game = session.get('game', {})

    if not game or game.get('step') != 'playing':

        return jsonify({'error': '游戏未开始'}), 400



    current_year = game.get('current_year', 0)



    # 尝试使用 LLM 批量生成事件和选择

    llm_result = None

    llm_override = session.get('llm_override')
    llm_error = ""

    enabled = llm_client.enabled or (session.get('llm_override') and session['llm_override'].get('enabled'))
    if enabled and world.get('use_llm'):

                    llm_result = llm_client.generate_events_batch(world, game, llm_override)



    events_data = []

    choices = []

    is_ended = False

    ending = None



    fortune = 100  # 初始满运势，首次生成后更新

    if llm_result and 'events' in llm_result and 'choices' in llm_result:

        events = llm_result['events']

        choices = llm_result['choices']

        # 提取运势值
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

                'year': year,

                'event': evt['text'],

                'age_icon': get_age_icon(year),

                'trait_changes': tc

            })
        wtc = llm_result.get('world_tag_changes', {}) or {}
        if wtc and events_data:
            events_data[-1]['world_tag_changes'] = wtc
        game_tags = game.get('world_tags', {})
        if not isinstance(game_tags, dict):
            game_tags = {}
        wtc = llm_result.get('world_tag_changes', {}) or {}
        if wtc:
            print(f'[LLM] world_tag_changes raw: {json.dumps(wtc, ensure_ascii=False)}')
            # 合并世界书变化：支持嵌套格式和点号格式
            _merge_world_tag_changes(game_tags, wtc)
            session['game']['world_tags'] = game_tags
            print(f'[LLM] world_tags merged: {json.dumps(game_tags, ensure_ascii=False, indent=2)}')

        if finished and finished != "false":

            is_ended = True

            ending = {

                'type': finished,

                'title': '一生结束',

                'text': epitaph or '你走完了这一生。',

                'summary': llm_result.get('summary', ''),

                'score': llm_result.get('score', 0)

            }

    else:

        # LLM 重试均失败，返回错误提示
        llm_error = "LLM 生成失败，请稍后重试"



    # 保存事件历史

    game['history'] = game.get('history', [])

    for evt_data in events_data:

        game['history'].append({

            'year': evt_data['year'],

            'event': evt_data['event'],

            'choice': None,

            'trait_changes': evt_data.get('trait_changes', {}),

            'world_tag_changes': evt_data.get('world_tag_changes', {}),

            'age_icon': evt_data.get('age_icon', '')

        })

        game['current_year'] = evt_data['year']

        # 应用每个事件的属性变化

        changes = evt_data.get('trait_changes', {}) or {}

        for trait, delta in changes.items():

            if trait in game.get('traits', {}):

                game['traits'][trait] = max(0, game['traits'][trait] + delta)



    game['pending_choices'] = choices

    session['game'] = game



    if is_ended:

        session['game']['step'] = 'ended'

        # 调用LLM生成人生总结评分

        eval_result = None

        if llm_client.enabled or (session.get('llm_override') and session['llm_override'].get('enabled')):
            eval_result = llm_client.generate_ending_evaluation(world, game, session.get('llm_override'))

        if eval_result:

            ending['score'] = eval_result.get('score', 0)

            ending['summary'] = eval_result.get('summary', '')

            ending['type'] = eval_result.get('type', 'normal')

            ending['title'] = eval_result.get('title', '一生结束')

            if not ending.get('text'):

                ending['text'] = eval_result.get('epitaph', '你走完了这一生。')

        session['game']['ending'] = ending

        # 保存游玩记录到文件

        save_game_record(world, game, ending)



    return jsonify({

        'events': events_data,

        'choices': choices if not is_ended else [],

        'ended': is_ended,

        'llm_error': llm_error if llm_error else None,
        'retry': bool(llm_error),  # LLM 失败时前端显示重试按钮
        'fortune': fortune,
        'world_tags': session.get('game', {}).get('world_tags')

    })





@app.route('/game/<world_id>/choose', methods=['POST'])

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





@app.route('/game/<world_id>/ending')

def game_ending(world_id):

    """结局页面 - 展示完整人生回顾"""

    if not check_entry():

        return render_template("error.html", message="请从首页开始游戏 🏠", back_url="/"), 403

    world = get_world(world_id)

    game = session.get('game', {})

    ending = game.get('ending', {

        'type': 'normal',

        'title': '一生结束',

        'text': '你的故事落幕了。'

    })

    history = game.get('history', [])

    traits = game.get('traits', {})

    talents = game.get('talents', [])

    background = game.get('background', '')



    # 计算寿命：最后一个事件年份 - 第一个事件年份
    history = game.get('history', [])
    if history:
        years = [h['year'] for h in history if 'year' in h]
        if years:
            lifespan = max(years) - min(years)
            if lifespan > 0:
                ending['lifespan'] = lifespan



    return render_template('ending.html',

        world=world,

        ending=ending,

        history=history,

        traits=traits,

        talents=talents,

        background=background,

        world_tags=game.get('world_tags', {}),

        time_unit=world.get('time_unit', '岁') if world else '岁')





@app.route('/game/export', methods=['GET'])

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



    # 生成文本格式

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



    export_text.append("【人生纪事】")
    time_unit = game.get('time_unit', '岁')
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
                        extra.append(f'{k}.{sk}: {"+" if sv > 0 else ""}{sv}')
                else:
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



    # 生成JSON格式

    export_json = {

        'world': world['name'],

        'gender': gender,

        'race': race,

        'talents': [t['name'] for t in talents],

        'traits': traits,

        'background': background,

        'history': history,

        'world_tags': game.get('world_tags', {}),

        'time_unit': game.get('time_unit', '岁'),

        'ending': game.get('ending'),

        'generated_at': datetime.now().isoformat()

    }



    # 返回JSON响应

    return jsonify({

        'text': '\n'.join(export_text),

        'json': export_json

    })





def get_world(world_id):

    """获取世界数据（支持自定义世界）"""

    world = next((w for w in WORLDS if w['id'] == world_id), None)

    if not world and world_id in ('custom', 'random'):

        from flask import session

        # 优先从 session['game'] 中获取（最可靠）
        game = session.get('game', {})
        world = game.get('custom_world') if game else None

        # fallback 到 session['custom_world']
        if not world:
            world = session.get('custom_world')

        if world:

            world['unlocked'] = True
            # 优先使用 session['game'] 中保存的世界名（防止丢失）
            if game.get('world_name') and world_id == 'random':
                world['name'] = game['world_name']

    return world





def save_game_record(world, game, ending):

    """保存游玩记录到 records 文件夹"""

    try:

        records_dir = Path(__file__).parent / 'records'

        records_dir.mkdir(exist_ok=True)



        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        world_name = world.get('name', 'unknown') if world else 'unknown'
        # 随机世界优先使用 session['game'] 中保存的名字
        if not world_name or world_name == 'unknown':
            world_name = game.get('world_name', '随机世界')

        player_name = game.get('player_name', '').strip()

        show_record = game.get('show_record', True)



        name_part = f'_{player_name}' if player_name else ''

        display_part = '' if show_record else '_nodisplay'

        filename = f'{timestamp}_{world_name}{name_part}{display_part}.json'



        record = {

            'saved_at': datetime.now().isoformat(),

            'world': world_name,

            'player_name': player_name if player_name else '',

            'gender': game.get('gender', {}).get('name', '未知'),

            'race': game.get('race', {}).get('name', '未知'),

            'custom_race': game.get('custom_race', ''),

            'custom_race_desc': game.get('custom_race_desc', ''),

            'destiny': game.get('custom_destiny', ''),

            'talents': [t['name'] for t in game.get('talents', [])],

            'traits': game.get('traits', {}),

            'background': game.get('background', ''),

            'world_tags': game.get('world_tags', {}),

            'time_unit': world.get('time_unit', '岁') if world else '岁',

            'ending_type': world.get('ending_type', '') if world else '',

            'history': [

                {

                    'year': h['year'],

                    'event': h['event'],

                    'choice': h.get('choice', ''),

                    'trait_changes': h.get('trait_changes', {}),

                    'world_tag_changes': h.get('world_tag_changes', {}),

                    'age_icon': h.get('age_icon', '')

                }

                for h in game.get('history', [])

            ],

            'ending': {

                'title': ending.get('title', ''),

                'text': ending.get('text', ''),

                'type': ending.get('type', 'normal'),

                'score': ending.get('score', 0),

                'summary': ending.get('summary', ''),

            },

            'lifespan': (lambda h: max([x['year'] for x in h]) - min([x['year'] for x in h]) if h else 0)(game.get('history', [])),

            'show_record': show_record,

        }



        filepath = records_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:

            json.dump(record, f, ensure_ascii=False, indent=2)



        # 使记录缓存失效
        _records_cache['data'] = None
        _records_cache['mtime'] = 0
        print(f'[Record] 已保存: {filepath}')

    except Exception as e:

        print(f'[Record] 保存失败: {e}')





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

    elif age < 70:

        return '👴'

    else:

        return '👴'





@app.route('/game/save', methods=['GET'])
def save_game():
    """导出当前游戏存档为JSON文件"""
    game = session.get('game', {})
    world_id = game.get('world_id', '')
    world = get_world(world_id) or {}
    history = game.get('history', [])
    if not game or not history:
        return jsonify({'error': '没有可保存的游戏进度'}), 400

    save_data = {
        'version': 1,
        'saved_at': datetime.now().isoformat(),
        'world_id': world_id,
        'world_name': world.get('name', '未知'),
        'player_name': game.get('player_name', ''),
        'gender': game.get('gender', {}),
        'race': game.get('race', {}),
        'custom_race': game.get('custom_race', ''),
        'custom_race_desc': game.get('custom_race_desc', ''),
        'custom_destiny': game.get('custom_destiny', ''),
        'talents': game.get('talents', []),
        'traits': game.get('traits', {}),
        'background': game.get('background', ''),
        'current_year': game.get('current_year', 0),
        'history': game.get('history', []),
        'world_tags': game.get('world_tags', {}),
        'step': game.get('step', 'playing'),
    }
    # 只有当最后一条历史记录还没有选择时，才保存 pending_choices
    history = game.get('history', [])
    if history and not history[-1].get('choice'):
        save_data['pending_choices'] = game.get('pending_choices', [])
    else:
        save_data['pending_choices'] = []
    return jsonify(save_data)

@app.route('/game/load', methods=['POST'])
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
            'gender': data.get('gender', {}),
            'race': data.get('race', {}),
            'custom_race': data.get('custom_race', ''),
            'custom_race_desc': data.get('custom_race_desc', ''),
            'custom_destiny': data.get('custom_destiny', ''),
            'talents': data.get('talents', []),
            'traits': data.get('traits', {}),
            'background': data.get('background', ''),
            'current_year': data.get('current_year', 0),
            'history': data.get('history', []),
            'world_tags': data.get('world_tags', {}),
            'step': 'playing',
            'show_record': True,
            'pending_choices': data.get('pending_choices', []),
        }
        session['entry_origin'] = 'home'
        return jsonify({'status': 'ok', 'next_step': '/game/' + data.get('world_id', '') + '/play'})
    except Exception as e:
        return jsonify({'error': f'存档读取失败: {e}'}), 400

@app.route('/api/llm-config', methods=['POST'])

def api_llm_config():

    """前端传入 LLM 设置，全部存到当前 session，不影响全局。
    分两类：
      - 生成参数（batch_min/batch_max/event_words/writing_style/max_tokens）：
        无论是否自定义都存入 override，覆盖全局默认值
      - 连接参数（api_base/api_key/model/temperature/top_p）：
        仅当自定义 LLM 开启且填了 api_key 时存入
    """

    data = request.json or {}
    # 填了 api_key 才算真正启用自定义 LLM
    on = data.get('enabled', False) and bool(data.get('api_key', '').strip())

    override = {'enabled': on}

    # 生成参数
    for key in ['event_words', 'writing_style']:
        v = data.get(key)
        if v: override[key] = v.strip()
    for key, cast in [('max_tokens', int), ('batch_min', int), ('batch_max', int)]:
        raw = data.get(key)
        if raw is not None:
            try: override[key] = cast(raw)
            except: pass

    # 连接参数（仅自定义 LLM 开启时）
    if on:
        for key in ['api_base', 'api_key', 'model']:
            v = data.get(key)
            if v: override[key] = v.strip()
        for key, cast in [('temperature', float), ('top_p', float)]:
            raw = data.get(key)
            if raw is not None:
                try: override[key] = cast(raw)
                except: pass

        # 自定义请求体：以后端 config 为基础，前端输入覆盖
        custom_body = dict(llm_client.custom_body)  # 后端默认
        if data.get('json_mode'):
            custom_body['response_format'] = {'type': 'json_object'}
        # 前端自定义请求体 JSON 输入
        raw_body = data.get('custom_body')
        if raw_body:
            try:
                frontend_body = json.loads(raw_body)
                custom_body.update(frontend_body)  # 前端覆盖后端
            except json.JSONDecodeError:
                pass
        override['custom_request_body'] = custom_body

    session['llm_override'] = override
    print(f"[LLM Config] 已更新: on={on}, override_keys={list(override.keys())}")

    return jsonify({'status': 'ok'})





# 记录缓存
_records_cache = {'data': None, 'mtime': 0}

@app.route('/api/records')
def api_records():
    """获取所有公开记录列表（带缓存）"""
    records_dir = Path(__file__).parent / 'records'
    if not records_dir.exists():
        return jsonify([])

    # 检查目录修改时间，缓存命中则直接返回
    dir_mtime = records_dir.stat().st_mtime if records_dir.exists() else 0
    if _records_cache['data'] is not None and _records_cache['mtime'] == dir_mtime:
        return jsonify(_records_cache['data'])

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
    return jsonify(result)





@app.route('/api/records/<path:filename>')

def api_record_detail(filename):

    """获取单条记录详情"""

    records_dir = Path(__file__).parent / 'records'

    filepath = records_dir / filename

    if not filepath.exists() or 'nodisplay' in filename:

        return jsonify({'error': '记录不存在'}), 404

    try:

        with open(filepath, 'r', encoding='utf-8') as f:

            data = json.load(f)

        return jsonify(data)

    except:

        return jsonify({'error': '读取失败'}), 500





@app.route('/records')

def records_page():

    """历史记录页面"""

    session['entry_origin'] = 'home'

    return render_template('records.html')





@app.route('/about')

def about():

    """关于页面"""

    return render_template('about.html', llm_config=LLM_CONFIG, llm_enabled=llm_client.enabled)





def cleanup_old_sessions():
    """清理超过24小时的旧session文件"""
    try:
        import time
        now = time.time()
        cutoff = 24 * 3600
        for f in SESSION_DIR.glob('*'):
            if f.is_file() and (now - f.stat().st_mtime) > cutoff:
                try:
                    f.unlink()
                    print(f'[Session] 已清理: {f.name}')
                except:
                    pass
    except Exception as e:
        print(f'[Session] 清理异常: {e}')


if __name__ == '__main__':

    port = CONFIG.get('app', {}).get('port', 5000)

    debug = CONFIG.get('app', {}).get('debug', True)

    # 启动时清理旧session
    cleanup_old_sessions()

    print("=" * 50)

    print("AI 人生重开手帐")

    print("=" * 50)

    print(f"LLM 状态: {'已启用' if llm_client.enabled else '未启用'}")

    if llm_client.enabled:

        print(f"API 地址: {LLM_CONFIG['api_base']}")

        print(f"模型: {LLM_CONFIG['model']}")

    print()

    print("\n配置文件: config.json")

    print("可直接修改 config.json 来配置 LLM 参数:")

    print("  llm.enabled: true")

    print("  llm.api_base: https://api.openai.com/v1")

    print("  llm.api_key: sk-xxx")

    print("  llm.model: gpt-4o")

    print("  llm.custom_request_body: { \"thinking\": true }")

    print("=" * 50)

    print()



    app.run(debug=debug, host='0.0.0.0', port=port)

