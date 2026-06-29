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

        '战斗': '⚔️', '源石技艺': '🔮', '战术': '🧠', '意志': '🔥',

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

        '战斗': '近身作战能力，影响生存和武力对抗',

        '源石技艺': '操控源石能量的天赋，影响施法能力',

        '战术': '战场局势的判断和指挥能力',

        '意志': '精神的坚韧程度，面对感染和压力的承受力',

    }

    return descs.get(trait, '')





app.jinja_env.globals.update(get_trait_icon=get_trait_icon)

app.jinja_env.globals.update(get_trait_desc=get_trait_desc)



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

        config['max_tokens'] = 512

    if 'custom_request_body' not in config:

        config['custom_request_body'] = {}



    return config



LLM_CONFIG = merge_config()




# ============ 世界书标签系统 ============

WORLD_TAG_DEFAULTS = {
    'cold_war': {
        'society': {'socialClass': '阶级分明', 'politicalStability': '暗流涌动', 'factionDensity': '两大阵营', 'legalSystem': '严格管制', 'educationLevel': '中等', 'familyStructure': '传统核心'},
        'environment': {'disasterFrequency': '低', 'climateType': '温带', 'terrainType': '城市为主', 'resourceAbundance': '中等'},
        'economy': {'economicSystem': '计划经济', 'techLevel': '冷战科技', 'resourceDistribution': '不均', 'tradeLevel': '有限'},
        'supernatural': {'existenceMode': '不存在', 'prevalence': '无', 'dangerLevel': '无', 'controllability': '无'},
        'demographics': {'racialComposition': '单一人类', 'populationDensity': '城市密集', 'language': '多语种', 'culturalDiversity': '中等'},
        'culturalFabric': {'values': '意识形态对立', 'religion': '受压制', 'art': '政治宣传', 'tradition': '逐渐消解'},
    },
    'arknights': {
        'society': {'socialClass': '分化严重', 'politicalStability': '动荡', 'factionDensity': '多势力并存', 'legalSystem': '混乱', 'educationLevel': '不均', 'familyStructure': '多样化'},
        'environment': {'disasterFrequency': '频繁', 'climateType': '多样', 'terrainType': '源石污染', 'resourceAbundance': '匮乏'},
        'economy': {'economicSystem': '混合制', 'techLevel': '源石科技', 'resourceDistribution': '极不均', 'tradeLevel': '有限'},
        'supernatural': {'existenceMode': '源石技艺', 'prevalence': '普遍', 'dangerLevel': '高', 'controllability': '需训练'},
        'demographics': {'racialComposition': '多种族', 'populationDensity': '不均', 'language': '通用语', 'culturalDiversity': '高'},
        'culturalFabric': {'values': '生存至上', 'religion': '多信仰', 'art': '实用主义', 'tradition': '正在重建'},
    },
    'warhammer40k': {
        'society': {'socialClass': '极端等级', 'politicalStability': '脆弱', 'factionDensity': '多阵营混战', 'legalSystem': '帝皇法典', 'educationLevel': '极低', 'familyStructure': '支离破碎'},
        'environment': {'disasterFrequency': '极高', 'climateType': '极端恶劣', 'terrainType': '巢都废土', 'resourceAbundance': '匮乏'},
        'economy': {'economicSystem': '帝国集权', 'techLevel': '倒退回中世纪', 'resourceDistribution': '极不均', 'tradeLevel': '星际有限'},
        'supernatural': {'existenceMode': '亚空间灵能', 'prevalence': '危险普遍', 'dangerLevel': '极高', 'controllability': '极难'},
        'demographics': {'racialComposition': '帝国异形混沌', 'populationDensity': '巢都密集', 'language': '低哥特语', 'culturalDiversity': '高度分化'},
        'culturalFabric': {'values': '生存与信仰', 'religion': '帝皇崇拜', 'art': '哥特黑暗', 'tradition': '僵化保守'},
    },
    'blue_archive_abydos': {
        'society': {'socialClass': '自治学园', 'politicalStability': '联邦瘫痪', 'factionDensity': '多学园加外部势力', 'legalSystem': '学园自治法', 'educationLevel': '高', 'familyStructure': '多样化'},
        'environment': {'disasterFrequency': '中等', 'climateType': '沙漠化', 'terrainType': '沙漠废墟', 'resourceAbundance': '匮乏'},
        'economy': {'economicSystem': '学园经济', 'techLevel': '先进', 'resourceDistribution': '不均', 'tradeLevel': '活跃'},
        'supernatural': {'existenceMode': '不适用', 'prevalence': '无', 'dangerLevel': '无', 'controllability': '无'},
        'demographics': {'racialComposition': '单一人类', 'populationDensity': '低', 'language': '通用语', 'culturalDiversity': '中等'},
        'culturalFabric': {'values': '青春与羁绊', 'religion': '无特定', 'art': '流行文化', 'tradition': '校园文化'},
    },
    'blue_archive_gamedev': {
        'society': {'socialClass': '自治学园', 'politicalStability': '联邦瘫痪', 'factionDensity': '多学园', 'legalSystem': '学园自治法', 'educationLevel': '高', 'familyStructure': '多样化'},
        'environment': {'disasterFrequency': '低', 'climateType': '温带', 'terrainType': '科技学园', 'resourceAbundance': '充足'},
        'economy': {'economicSystem': '学园经济', 'techLevel': '尖端', 'resourceDistribution': '偏重理工', 'tradeLevel': '活跃'},
        'supernatural': {'existenceMode': '不适用', 'prevalence': '无', 'dangerLevel': '无', 'controllability': '无'},
        'demographics': {'racialComposition': '单一人类', 'populationDensity': '高', 'language': '通用语', 'culturalDiversity': '中等'},
        'culturalFabric': {'values': '创作与热情', 'religion': '无特定', 'art': '游戏御宅文化', 'tradition': '科技与传统并存'},
    },
}


def format_world_tags(tags):
    if not tags:
        return ''
    labels = {
        'society': '【社会结构】',
        'environment': '【自然环境】',
        'economy': '【经济体系】',
        'supernatural': '【超自然】',
        'demographics': '【人口构成】',
        'culturalFabric': '【文化面貌】',
    }
    lines = ['\n=== 世界书 ===']
    for key, label in labels.items():
        cat = tags.get(key, {})
        if cat:
            parts = [f'{k}: {v}' for k, v in cat.items()]
            lines.append(f'{label}  {" | ".join(parts)}')
    return '\n'.join(lines)


def get_world_tags(world):
    wid = world.get('id', '')
    tags = WORLD_TAG_DEFAULTS.get(wid)
    if tags:
        return tags
    parent = world.get('parent')
    if parent and parent in WORLD_TAG_DEFAULTS:
        return WORLD_TAG_DEFAULTS[parent]
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



# 命运底色

DESTINY_THEMES = [

    {

        'id': 'grassroot',

        'name': '草根成长',

        'icon': '🌱',

        'description': '普通起点，靠自己向上走'

    },

    {

        'id': 'fated_love',

        'name': '命定之恋',

        'icon': '💖',

        'description': '青涩相遇，一生相守或错过'

    },

    {

        'id': 'ordinary_happiness',

        'name': '平凡幸福',

        'icon': '🏠',

        'description': '不求逆袭，只求日子温暖'

    },

    {

        'id': 'multiverse_echo',

        'name': '诸天回响',

        'icon': '🌌',

        'description': '听见诸世自己的回声'

    },

    {

        'id': 'system',

        'name': '随身系统',

        'icon': '📜',

        'description': '成长目标清晰，但奖励有代价'

    },

    {

        'id': 'bloodline',

        'name': '血脉传承',

        'icon': '🩸',

        'description': '身世成谜，力量慢慢补全'

    },

    {

        'id': 'heaven_born',

        'name': '天地所生',

        'icon': '🌄',

        'description': '有来处之谜，也要落脚人间'

    },

    {

        'id': 'reincarnation_wisdom',

        'name': '异世宿慧',

        'icon': '🧭',

        'description': '带着前尘，重新理解世界'

    },

    {

        'id': 'red_sky_love',

        'name': '红尘知己',

        'icon': '🌸',

        'description': '多段羁绊，注定难以两全'

    },

]



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

        'id': 'cold_war',

        'icon': '☢️',

        'name': '冷战风云',

        'description': '核阴影下，铁幕两侧',

        'color': '#e63946',

        'unlocked': True,

        'traits': ['勇气', '智慧', '忠诚', '运气'],

        'trait_max': 10,

        'trait_total': 12,

        'use_llm': True,

        'prompt': '你是一个间谍小说的叙事者。玩家在冷战时期开始了自己的故事。'

                  '请根据玩家的属性和当前年份，生成一个简短的间谍事件描述（50字左右）。',

        'events': [

            '你出生在冷战高峰期。',

            '你的童年在紧张的氛围中度过。',

            '你的父亲是一名军官，从小你就听着他的故事长大。',

            '你在学校里成绩优异，表现突出。',

            '你被招募进了情报部门。',

            '训练很艰苦，但你坚持下来了。',

            '你被派往敌国执行任务。',

            '你发现了一个惊天阴谋。',

            '你的身份暴露了，遭到追捕。',

            '你必须做出选择：忠诚或良知。',

            '你成为了冷战中一个被遗忘的英雄。',

        ]

    },

    {

        'id': 'kingdom',

        'icon': '🏯',

        'name': '三国逐鹿',

        'description': '乱世群雄，逐鹿中原',

        'color': '#f4a261',

        'unlocked': False,

        'locked_icon': '🔒',

        'traits': ['武勇', '谋略', '仁德', '天命'],

        'events': []

    },

    {

        'id': 'abyss',

        'icon': '🐙',

        'name': '深渊低语',

        'description': '直面深渊，深渊亦回望',

        'color': '#2d3436',

        'unlocked': False,

        'locked_icon': '🔒',

        'traits': ['理智', '勇气', '感知', '运气'],

        'events': []

    },

    {

        'id': 'crusade',

        'icon': '✝️',

        'name': '十字军纪元',

        'description': '圣战号角响彻东方',

        'color': '#d4a373',

        'unlocked': False,

        'locked_icon': '🔒',

        'traits': ['信仰', '武勇', '统帅', '魅力'],

        'events': []

    },

    {

        'id': 'galaxy',

        'icon': '🚀',

        'name': '银河纪元',

        'description': '群星是征途，也是坟场',

        'color': '#00b4d8',

        'unlocked': False,

        'locked_icon': '🔒',

        'traits': ['基因', '精神', '运气', '能力'],

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

        """发送请求到 LLM API（支持 session 覆写）"""

        cfg = override or {}

        url = f"{cfg.get('api_base', self.config['api_base']).rstrip('/')}/chat/completions"

        body = cfg.get('custom_request_body', {}) if override else self.custom_body

        request_body = {

            'model': cfg.get('model', self.config['model']),

            'messages': messages,

            'temperature': float(cfg.get('temperature', self.config['temperature'])),

            'max_tokens': max(cfg.get('max_tokens', self.config['max_tokens']), 2048),

        }

        if body:

            request_body.update(body)



        # 前端设置了 json_mode 才加 response_format

        if cfg.get('json_mode', self.config.get('json_mode')):

            request_body['response_format'] = {'type': 'json_object'}



        response = requests.post(

            url,

            headers={

                'Authorization': f"Bearer {cfg.get('api_key', self.config['api_key'])}",

                'Content-Type': 'application/json',

            },

            json=request_body,

            timeout=60

        )



        return response



    def generate_events_batch(self, world, game_state, override=None):

        """使用 LLM 生成批量人生事件 + 一个选择点，返回JSON格式"""

        if not self.enabled:

            return None



        try:

            traits = game_state.get('traits', {})

            current_year = game_state.get('current_year', 0)

            time_unit = world.get('time_unit', '岁')

            time_unit = world.get('time_unit', '岁')

            history = game_state.get('history', [])

            talents = game_state.get('talents', [])

            background = game_state.get('background', '')



            trait_text = '，'.join([f'{k}: {v}' for k, v in traits.items()])

            batch_min = self.config.get('batch_min', 1)

            batch_max = self.config.get('batch_max', 3)

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

            race_text = ''

            if custom_race:

                race_text = f'自定义种族：{custom_race}'

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



            system_prompt = f"""{world.get('prompt', '你是一个人生模拟游戏的叙事者。')}



核心规则：

1. 每次生成 {batch_size} 年的连续年度事件，每个事件的year不一定唯一，可以重复

2. 每个事件语言简洁，30-60字

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



JSON格式（严格遵守）：

{{

  "events": [

    {{"year": {current_year + 1}, "text": "事件描述", "trait_changes": {{{tc_example}}}}},

    {{"year": {current_year + 2}, "text": "事件描述", "trait_changes": {{{tc_example}}}}},

    ...

  ],

  "choices": [

    {{"text": "选择A", "mood": "positive/negative/neutral"}},

    {{"text": "选择B", "mood": "positive/negative/neutral"}},

    {{"text": "选择C", "mood": "positive/negative/neutral"}}

  ],

  "finished": "false",

  "epitaph": "若finished不为false则写任务总结/墓志铭"

}}



finished字段取值说明：
- 普通世界（岁单位）："true" = 故事结束（寿命终了/剧情终点），"false" = 继续
重要：不要回避失败结局。如果玩家选择了高风险选项或剧情走向失败条件，请大胆给出"fail"结局。
- 注意：当finished不为false时，最后一个事件必须是明确的结局描述，不能留悬念或问号。
失败和成功的结局同样有故事价值。玩家自定义输入享有最高优先级，写了什么就发生什么，不得弱化。


注意：

- events中同年可以有多个事件，前端会合并显示

- 返回纯粹JSON，不要其他文字

- events数组长度 {batch_size}

"""



            user_prompt = f"""世界设定：{world['name']}

{race_text}

玩家天赋（含属性加成）：{talent_text}

玩家最终属性：{trait_text}

当前进度：{current_year} {time_unit}



=== 完整人生历史（必须严格参考，不能矛盾） ===

{history_text}

==========



请基于以上所有历史，生成接下来 {batch_size} 年的人生事件和最终的选择。

特别注意：用户的自定义输入必须不折不扣执行；如果用户选了自杀/赴死等自我毁灭选项，本批必须让角色死亡。"""



            messages = [

                {'role': 'system', 'content': system_prompt},

                {'role': 'user', 'content': user_prompt}

            ]



            response = self._make_request(messages, override)



            if response.status_code == 200:

                result = response.json()

                content = result['choices'][0]['message']['content'].strip()

                # 移除 markdown 代码块包裹

                if '```' in content:

                    content = content.replace('```json', '').replace('```', '').strip()

                try:

                    return json.loads(content)

                except:

                    try:

                        json_start = content.find('{')

                        json_end = content.rfind('}') + 1

                        if json_start >= 0 and json_end > json_start:

                            json_str = content[json_start:json_end]

                            return json.loads(json_str)

                    except:

                        pass

                print(f"[LLM] JSON解析失败 (前500字): {content[:500]}")

                return None

            else:

                err_msg = response.text[:200] if response.text else '无响应'

                print(f"[LLM] API错误 {response.status_code}: {err_msg}")

                return None



        except Exception as e:

            print(f"[LLM] 调用异常: {e}")

            return None



    def generate_background(self, world, game_state, override=None):

        """生成身世介绍"""

        if not self.enabled:

            return None



        try:

            traits = game_state.get('traits', {})

            talents = game_state.get('talents', [])

            gender = game_state.get('gender', {}).get('name', '未知')

            race = game_state.get('race', {}).get('name', '未知')



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

请根据玩家的天赋和属性，生成一段身世介绍（150字左右）。

要求：

- 语言要具有叙事感，像小说开头

- 要结合天赋和属性

- 以JSON格式返回：{"background": "身世介绍内容"}

"""



            user_prompt = f"""世界设定：{world['name']}

性别：{gender}

种族：{race}

天赋：{talent_text}

属性：{trait_text}



请生成身世介绍："""



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

                    return json_result.get('background', content)

                except:

                    try:

                        json_start = content.find('{')

                        json_end = content.rfind('}') + 1

                        if json_start >= 0 and json_end > json_start:

                            json_str = content[json_start:json_end]

                            json_result = json.loads(json_str)

                            return json_result.get('background', content)

                    except:

                        pass

                return content

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

    return render_template('world.html', world=world)





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

                              genders=GENDERS, races=RACES, destinies=DESTINY_THEMES)



    if request.method == 'POST':

        data = request.json

        custom_race = data.get('custom_race', '')

        race_obj = None

        if custom_race:

            race_obj = {'id': 'custom', 'name': custom_race, 'icon': '✨', 'unlocked': True}



        session['game'] = {

            'world_id': 'custom',

            'gender': next((g for g in GENDERS if g['id'] == data.get('gender')), GENDERS[0]),

            'race': race_obj or next((r for r in RACES if r['id'] == data.get('race')), RACES[0]),

            'custom_race': custom_race if custom_race else None,

            'destiny_theme': next((d for d in DESTINY_THEMES if d['id'] == data.get('destiny')), None),

            'step': 'identity_done'

        }

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

        'step': 'talents_done'

    }

    return render_template('traits.html', world=world, talents=[])





@app.route('/game/<world_id>/identity', methods=['GET', 'POST'])

def game_identity(world_id):

    """身份设定页面"""

    world = get_world(world_id)

    if not world or not world['unlocked']:

        return render_template('error.html', message='这个世界尚未解锁 🔒'), 404



    if request.method == 'POST':

        data = request.json

        session['game'] = {

            'world_id': world_id,

            'gender': next((g for g in GENDERS if g['id'] == data.get('gender')), GENDERS[0]),

            'race': next((r for r in RACES if r['id'] == data.get('race')), RACES[0]),

            'destiny_theme': next((d for d in DESTINY_THEMES if d['id'] == data.get('destiny')), None),

            'step': 'identity_done'

        }

        return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/talents'})



    return render_template('identity.html', world=world,

                          genders=GENDERS, races=RACES, destinies=DESTINY_THEMES)





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



    # 身世只用生成一次，存到session后复用

    if not game.get('background'):

        background = None

        if world.get('time_unit') == '周':

            if world_id.find('abydos') >= 0:

                background = '你是夏莱的老师，接到了阿拜多斯对策委员会的求助信。这所濒临废校的学校背负着巨额债务，仅剩五名学生还在坚持。你决定前往阿拜多斯自治区。'

            elif world_id.find('gamedev') >= 0:

                background = '你是夏莱的老师，游戏开发部向夏莱发出了求助信。这个即将被废部的社团只有三名成员，她们开发的游戏被评为年度最烂。你决定前往千年科技学院。'

            else:

                background = '你来到了基沃托斯，作为夏莱的老师，新的故事即将开始。'

        elif llm_client.enabled or (session.get('llm_override') and session['llm_override'].get('enabled')):
            background = llm_client.generate_background(world, game, session.get('llm_override'))

        if not background:

            background = "你出生在一个普通的家庭，从小就表现出一些与众不同的特质。"

        session['game']['background'] = background

    else:

        background = game['background']



    if request.method == 'POST':

        data = request.json or {}

        pn = (data.get('player_name', '') or '')[:12]

        session['game']['player_name'] = pn

        session['game']['show_record'] = data.get('show_record', True)

        session['game']['current_year'] = 0

        session['game']['history'] = []

        session['game']['step'] = 'playing'

        return jsonify({'status': 'ok', 'next_step': '/game/' + world_id + '/play'})



    return render_template('preview.html', world=world, game=game, background=background)





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



    return render_template('game.html', world=world, game=session.get('game', {}))





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



    if llm_result and 'events' in llm_result and 'choices' in llm_result:

        events = llm_result['events']

        choices = llm_result['choices']

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



        if finished and finished != "false":

            is_ended = True

            ending = {

                'type': 'normal',

                'title': '一生结束',

                'text': epitaph or '你走完了这一生。',

                'summary': llm_result.get('summary', ''),

                'score': llm_result.get('score', 0)

            }

    else:

        # LLM失败时的后备：按年龄生成通用事件，不再取模循环

        age_events = {

            (0, 3): '你还很小，对世界充满好奇。',

            (3, 7): '你在玩耍和探索中度过了童年。',

            (7, 12): '你开始了学生生涯，认识了许多朋友。',

            (12, 15): '你进入了青春期，开始有了自己的主见。',

            (15, 18): '你在学业和成长中度过。',

            (18, 22): '你成年了，开始为自己的未来做打算。',

            (22, 30): '你在社会中打拼，逐渐站稳脚跟。',

            (30, 40): '你的事业和生活进入了稳定期。',

            (40, 50): '人到中年，你开始回顾过去，思考未来。',

            (50, 60): '你变得更加沉稳，珍惜身边的一切。',

            (60, 70): '你进入了晚年，开始享受平静的生活。',

            (70, 80): '你在安详中度过每一天。',

        }

        num_events = random.randint(3, 5)

        for i in range(num_events):

            year = current_year + i + 1

            if year >= 80:

                is_ended = True

                ending = {'type': 'normal', 'title': '寿终正寝', 'text': '你走完了平静的一生。'}

                break

            event_text = f'第 {year} 年，平淡地度过了。'

            for (lo, hi), text in age_events.items():

                if lo <= year < hi:

                    event_text = text

                    break

            events_data.append({

                'year': year,

                'event': event_text,

                'age_icon': get_age_icon(year)

            })

        choices = [

            {'text': '接受这一切，继续前行', 'mood': 'neutral'},

            {'text': '积极争取，改变现状', 'mood': 'positive'},

            {'text': '感到无奈，随遇而安', 'mood': 'negative'}

        ]



    # 保存事件历史

    game['history'] = game.get('history', [])

    for evt_data in events_data:

        game['history'].append({

            'year': evt_data['year'],

            'event': evt_data['event'],

            'choice': None

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

        'llm_error': llm_error if llm_error else None

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



    # 计算寿命

    lifespan = game.get('current_year', 0)

    if lifespan > 0:

        ending['lifespan'] = lifespan



    return render_template('ending.html',

        world=world,

        ending=ending,

        history=history,

        traits=traits,

        talents=talents,

        background=background)





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

    for record in history:

        event_text = record.get('event', '')

        choice_text = record.get('choice', '')

        year = record.get('year', '')

        export_text.append(f"{year:3d} 岁: {event_text}")

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

    if not world and world_id == 'custom':

        from flask import session

        world = session.get('custom_world')

        if world:

            world['unlocked'] = True

    return world





def save_game_record(world, game, ending):

    """保存游玩记录到 records 文件夹"""

    try:

        records_dir = Path(__file__).parent / 'records'

        records_dir.mkdir(exist_ok=True)



        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        world_name = world.get('name', 'unknown') if world else 'unknown'

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

            'destiny': game.get('destiny_theme', {}).get('name', ''),

            'talents': [t['name'] for t in game.get('talents', [])],

            'traits': game.get('traits', {}),

            'background': game.get('background', ''),

            'history': [

                {

                    'year': h['year'],

                    'event': h['event'],

                    'choice': h.get('choice', '')

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

            'lifespan': game.get('current_year', 0),

            'show_record': show_record,

        }



        filepath = records_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:

            json.dump(record, f, ensure_ascii=False, indent=2)



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





@app.route('/api/llm-config', methods=['POST'])

def api_llm_config():

    """前端传入 LLM 设置，存到当前 session"""

    data = request.json or {}
    on = data.get('enabled', False)
    if on:
        override = {'enabled': True}
        for key in ['api_base', 'api_key', 'model']:
            v = data.get(key)
            if v: override[key] = v.strip()
        raw = data.get('temperature')
        if raw:
            try: override['temperature'] = float(raw)
            except: pass
        raw = data.get('max_tokens')
        if raw:
            try: override['max_tokens'] = int(raw)
            except: pass
        body = {}
        raw = data.get('top_p')
        if raw:
            try: body['top_p'] = float(raw)
            except: pass
        if data.get('json_mode'):
            body['response_format'] = {'type': 'json_object'}
        if body:
            override['custom_request_body'] = body
        session['llm_override'] = override
    else:
        session.pop('llm_override', None)

    if data.get('temperature'):

        try:

            llm_client.config['temperature'] = float(data['temperature'])

        except: pass

    if data.get('max_tokens'):

        try:

            llm_client.config['max_tokens'] = int(data['max_tokens'])

        except: pass

    if data.get('top_p'):

        try:

            llm_client.custom_body['top_p'] = float(data['top_p'])

        except: pass

    if data.get('batch_min'):

        try:

            llm_client.config['batch_min'] = int(data['batch_min'])

        except: pass

    if data.get('batch_max'):

        try:

            llm_client.config['batch_max'] = int(data['batch_max'])

        except: pass

    if 'json_mode' in data:

        llm_client.config['json_mode'] = bool(data['json_mode'])

    llm_client.enabled = True

    print(f"[LLM Config] 已更新: model={llm_client.config['model']}")

    return jsonify({'status': 'ok'})





@app.route('/api/records')

def api_records():

    """获取所有公开记录列表"""

    records_dir = Path(__file__).parent / 'records'

    if not records_dir.exists():

        return jsonify([])



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





if __name__ == '__main__':

    port = CONFIG.get('app', {}).get('port', 5000)

    debug = CONFIG.get('app', {}).get('debug', True)



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

