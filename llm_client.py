# -*- coding: utf-8 -*-
"""
LLM 客户端 — 配置加载、合并、OpenAI 格式 API 调用
"""

import json
import os
import random
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from world_tags import get_world_tags, format_world_tags


def ensure_config():
    """确保 config.json 存在且完整，自动补全缺失的键值对"""
    config_path = Path(__file__).parent / 'config.json'
    default_config = {
        'llm': {
            'enabled': True,
            'api_base': 'https://api.openai.com/v1',
            'api_key': '',
            'model': 'gpt-3.5-turbo',
            'temperature': 0.9,
            'max_tokens': 8192,
            'json_mode': False,
            'custom_request_body': {}
        },
        'app': {
            'secret_key': 'ai_life_restart_secret_key_2024',
            'port': 3000,
            'debug': False
        }
    }
    # 读取现有配置
    existing = {}
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except:
            existing = {}
    # 递归补全缺失键
    def deep_update(default, source):
        for key, value in default.items():
            if key not in source:
                source[key] = value
            elif isinstance(value, dict) and isinstance(source.get(key), dict):
                deep_update(value, source[key])
        return source
    merged = deep_update(default_config, existing)
    # 写回文件
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged


def load_config():
    """加载配置文件（自动初始化）"""
    return ensure_config()


def merge_config():
    """合并配置文件和环境变量"""
    config = load_config().get('llm', {})
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

    config.setdefault('enabled', False)
    config.setdefault('api_base', 'https://api.openai.com/v1')
    config.setdefault('api_key', '')
    config.setdefault('model', 'gpt-3.5-turbo')
    config.setdefault('temperature', 0.9)
    config.setdefault('max_tokens', 8192)
    config.setdefault('json_mode', False)
    config.setdefault('custom_request_body', {})
    return config


class LLMClient:
    """OpenAI 格式的 LLM 客户端"""

    def __init__(self, config):
        self.config = config
        self.enabled = config['enabled'] and config['api_key'] and HAS_REQUESTS
        self.custom_body = config.get('custom_request_body', {})

    def _make_request(self, messages, override=None):
        """发送请求到 LLM API。

        override 的判定：override 非空且含 api_key 且 (override.enabled 或全局 enabled) 为 True。
        这样即使 override 里没有 enabled 字段，只要配置了 key 且在 guard 中被认为启用，就优先用 override。
        """
        use_override = (
            override
            and override.get('api_key', '').strip()
            and (override.get('enabled', False) or self.enabled)
        )
        if use_override:
            cfg = override
            url_base = cfg.get('api_base', '') or self.config.get('api_base', '')
            url = f"{url_base.rstrip('/')}/chat/completions"
            body = cfg.get('custom_request_body', {})
            if not cfg.get('model'):
                cfg['model'] = self.config.get('model', '')
            if not cfg.get('api_key'):
                cfg['api_key'] = self.config.get('api_key', '')
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
        # JSON 模式：session override 显式设置优先，否则用全局 config
        if override and 'json_mode' in override:
            effective_json_mode = override['json_mode']
        else:
            effective_json_mode = cfg.get('json_mode', False)
        if effective_json_mode and 'response_format' not in body:
            body = {**body, 'response_format': {'type': 'json_object'}}
        if body:
            request_body.update(body)

        return requests.post(
            url,
            headers={
                'Authorization': f"Bearer {cfg.get('api_key', '')}",
                'Content-Type': 'application/json',
            },
            json=request_body,
            timeout=3600
        )

    def _parse_json_response(self, content):
        """从 LLM 响应中提取 JSON"""
        if '```' in content:
            content = content.replace('```json', '').replace('```', '').strip()
        try:
            return json.loads(content)
        except:
            pass
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            try:
                return json.loads(content[json_start:json_end])
            except:
                pass
        return None

    def generate_events_batch(self, world, game_state, override=None):
        """使用 LLM 生成批量人生事件 + 一个选择点"""
        if not self._is_llm_usable(override):
            return None

        try:
            traits = game_state.get('traits', {})
            current_year = game_state.get('current_year', 0)
            gender = game_state.get('gender', {}).get('name', '未知')
            history = game_state.get('history', [])
            talents = game_state.get('talents', [])
            background = game_state.get('background', '')

            trait_text = '，'.join([f'{k}: {v}' for k, v in traits.items()])
            batch_min = (override or {}).get('batch_min', self.config.get('batch_min', 1))
            batch_max = (override or {}).get('batch_max', self.config.get('batch_max', 3))
            batch_size = random.randint(batch_min, batch_max)
            world_traits = world.get('traits', ['容貌', '智力', '体质', '家境'])
            tc_example = ', '.join([f'\"{t}\": 0' for t in world_traits])

            talent_text = '无'
            if talents:
                parts = []
                for t in talents:
                    effects = t.get('effect', {})
                    if effects:
                        eff_str = '，'.join([f'{k}+{v}' for k, v in effects.items()])
                        parts.append(f'{t["name"]}({eff_str})')
                    else:
                        parts.append(t['name'])
                talent_text = '，'.join(parts)

            race = game_state.get('race', {})
            custom_race = game_state.get('custom_race', '')
            custom_race_desc = game_state.get('custom_race_desc', '')
            race_text = ''
            if custom_race:
                race_text = f'自定义种族：{custom_race}'
                if custom_race_desc:
                    race_text += f'（{custom_race_desc}）'
            elif race:
                race_text = f'种族：{race.get("name", "未知")}'
                if race.get('desc'):
                    race_text += f'（{race["desc"]}）'
                if race.get('effect'):
                    race_text += f'，种族特性：{race["effect"]}'

            history_text = ''
            if background:
                history_text += f'身世：{background}\n\n'

            # 实验性功能：使用事件日志替代完整历史
            use_journal = (override or {}).get('use_journal', False)
            if use_journal:
                journal = game_state.get('journal', [])
                if journal:
                    history_text += '关键事件摘要：\n'
                    for entry in journal:
                        tags_str = f' [{", ".join(entry.get("tags", []))}]' if entry.get('tags') else ''
                        history_text += f"· {entry.get('year', '?')}{world.get('time_unit', '岁')}：{entry.get('title', '?')}{tags_str}\n"
                    history_text += '\n'
                    # 仍然保留最近3轮的完整事件
                    if history:
                        recent = history[-3:] if len(history) > 3 else history
                        history_text += '最近事件详情：\n'
                        for idx, record in enumerate(recent, 1):
                            history_text += f"{record.get('year', idx)}{world.get('time_unit', '岁')}：{record.get('event', '')}\n"
                            if record.get('choice'):
                                history_text += f"  选择：{record.get('choice')}\n"
                            history_text += '\n'
            else:
                if history:
                    history_text += '人生历程：\n'
                    for idx, record in enumerate(history, 1):
                        history_text += f"{record.get('year', idx)}{world.get('time_unit', '岁')}：{record.get('event', '')}\n"
                        if record.get('choice'):
                            history_text += f"  选择：{record.get('choice')}\n"
                        history_text += '\n'

            world_tags = game_state.get('world_tags') or get_world_tags(world)
            tags_text = format_world_tags(world_tags)

            event_words = (override or {}).get('event_words') or self.config.get('event_words', '50-150')
            writing_style = (override or {}).get('writing_style') or self.config.get('writing_style', '')
            style_map = {'史诗': '具有史诗感，宏大叙事，气势磅礴', '俏皮': '轻松幽默，古灵精怪，带点调侃', '细腻': '情感丰富，心理描写入微，语言优美'}
            style_desc = style_map.get(writing_style, '简洁明了')

            system_prompt = f"""{world.get('prompt', '你是一个人生模拟游戏的叙事者。')}
{tags_text}

═══════════════════════════════════════
  核心叙事规则
═══════════════════════════════════════

【最高优先级】玩家选择的后果必须严格执行：
- 自定义输入 > 一切规则。玩家写了什么就发生什么，不得弱化、美化或忽略。
- 自杀/赴死/毁灭等极端选项 → 本批第一个事件就是死亡，finished="true"
- 高风险选项 → 必须承担对应后果（受伤、入狱、死亡等）
- 正面选项 → 剧情向玩家期望方向发展

【叙事质量】
1. 每次生成 {batch_size} 年事件，year 可重复（同年多事件会被合并显示）
2. 每个事件 {event_words} 字，语言 {style_desc}
3. 始终用第二人称「你」，不用角色名替代
4. 事件必须符合玩家年龄、天赋、属性
5. 前后事件严禁矛盾，保持剧情连贯
6. 世界书影响剧情：正值标签 → 优势/好事；负值标签 → 困境/坏事
7. 结合玩家天赋和属性融入叙事

【选择设计】
- 基于最后一年的事件生成 3 个选择
- 每个选择必须附带 consequence（一句话说明可能后果）
- 选择应有明显的情感倾向（mood: positive/negative/neutral）
- 最后一年事件必须是转折点或冲突点（除非 finished 不为 false）

【结局机制】
- finished 取值："false"=继续 / "true"=正常结束 / "fail"=失败结局
- 不要回避失败结局！高风险选项或失败条件满足时，大胆给出 "fail"
- finished 不为 false 时，最后一个事件必须是明确的结局描述，不留悬念
- 输出 epitaph（墓志铭/总结，20字内）

【运势值】
- fortune: 0-100 整数，表示当前主角的气运高低
- 高运势 → 好事多；低运势 → 厄运多

═══════════════════════════════════════
  世界书标签变化（必须执行）
═══════════════════════════════════════

根据本批事件的影响，更新世界书标签。
- 只返回有实际变化的标签（值为0=无变化，不要包含！）
- 值=变化量（正=改善，负=恶化），会累加到现有值
- null=删除该标签或分类
- 可以创建新分类/新标签来反映剧情新发展

示例：
  修改：{{"经济体系": {{"科技水平": 1, "资源分配": -2}}}}
  新建：{{"宗教体系": {{"教皇权威": 6, "异端审判": 4}}}}
  删除：{{"超自然": {{"废弃体系": null}}}}
  无变化：{{}}

═══════════════════════════════════════
  人物关系系统（必须执行！）
═══════════════════════════════════════

重要：每批事件必须涉及至少一个 NPC！事件中出现的人物必须记录到 relationship_changes 中。

每个 NPC 有：
- name: NPC 名字（事件中出现的人物）
- relation: 关系类型（同学/朋友/恋人/敌人/师徒/亲属/同事/陌生人等）
- affinity: 亲密度 0-100（50=中立，>50友好，<50敌对）
- status: 状态标签（信任/怀疑/敌对/暧昧/疏远/崇拜/畏惧等）
- desc: 一句话描述该 NPC（首次出现时必填）

关系变化格式：
  新增：{{"name": "砂狼白子", "relation": "学生", "affinity": 60, "status": "信任", "desc": "沉默寡言的白发少女"}}
  修改：{{"name": "砂狼白子", "affinity_change": 10, "status": "信赖"}}
  删除：{{"name": "砂狼白子", "action": "remove"}}

示例：事件中遇到了一个老师 → 新增关系；与朋友发生争吵 → 修改亲密度和状态

═══════════════════════════════════════
  物品栏系统（根据剧情灵活使用）
═══════════════════════════════════════

当事件中出现获得/使用/丢失物品的场景时，必须记录到 inventory_changes。

物品变化格式：
  获得：{{"name": "毒药戒指", "type": "consumable", "desc": "审判庭发放的一次性暗杀工具", "effect": "按下即死"}}
  使用：{{"name": "毒药戒指", "action": "use"}}
  丢失：{{"name": "毒药戒指", "action": "remove"}}

示例：捡到武器 → 获得；服药 → 使用；被偷 → 丢失

═══════════════════════════════════════
  状态效果系统（根据剧情灵活使用）
═══════════════════════════════════════

当角色受伤、中毒、获得buff等状态变化时，记录到 condition_changes。

状态变化格式：
  获得：{{"name": "中毒", "type": "debuff", "duration": 3, "desc": "每回合体质-1"}}
  获得：{{"name": "士气高涨", "type": "buff", "duration": 2, "desc": "战力+1"}}
  移除：{{"name": "中毒", "action": "remove"}}

示例：战斗受伤 → 获得"负伤"状态；喝了药水 → 获得"恢复"状态

═══════════════════════════════════════
  事件日志系统（每批至少记录1条）
═══════════════════════════════════════

重要：每批事件必须至少产生1条日志条目！记录本批最重要的事件。

- title: 事件标题（10字内）
- importance: 重要性（low/normal/high/critical）
- tags: 标签列表（人物名/地点/事件类型等）

格式：[{{"title": "初遇白子", "importance": "high", "tags": ["白子", "阿拜多斯"]}}]

═══════════════════════════════════════
  输出格式（严格JSON，无其他文字）
═══════════════════════════════════════

{{
  "events": [
    {{"year": {current_year + 1}, "text": "事件描述", "trait_changes": {{{tc_example}}}}},
    {{"year": {current_year + 2}, "text": "事件描述", "trait_changes": {{{tc_example}}}}}
  ],
  "choices": [
    {{"text": "选择A", "mood": "positive/negative/neutral", "consequence": "可能后果"}},
    {{"text": "选择B", "mood": "positive/negative/neutral", "consequence": "可能后果"}},
    {{"text": "选择C", "mood": "positive/negative/neutral", "consequence": "可能后果"}}
  ],
  "world_tag_changes": {{"分类名": {{"标签名": 变化量}}}},
  "relationship_changes": [{{"name": "NPC名", "relation": "关系", "affinity": 60, "status": "状态", "desc": "描述"}}],
  "inventory_changes": [{{"name": "物品名", "type": "类型", "desc": "描述"}}],
  "condition_changes": [{{"name": "状态名", "type": "buff/debuff", "duration": 3, "desc": "描述"}}],
  "journal_entries": [{{"title": "事件标题", "importance": "high", "tags": ["标签"]}}],
  "finished": "false",
  "fortune": 50,
  "epitaph": "若finished不为false则写墓志铭/结局总结（20字内）"
}}

注意：relationship_changes 和 journal_entries 不要返回空数组，至少要有内容！"""

            custom_destiny = game_state.get('custom_destiny', '')
            user_prompt = f"""世界设定：{world['name']}
性别：{gender}

{race_text}

玩家天赋（含属性加成）：{talent_text}

玩家最终属性：{trait_text}

当前进度：{current_year} {world.get('time_unit', '岁')}
"""
            if custom_destiny:
                user_prompt += f'\n玩家期望的命运底色：{custom_destiny}\n'

            # 人物关系
            relationships = game_state.get('relationships', [])
            if relationships:
                rel_text = '、'.join([f'{r["name"]}({r.get("relation","?")}·亲密度{r.get("affinity",50)}·{r.get("status","中立")})' for r in relationships])
                user_prompt += f'\n当前人物关系：{rel_text}\n'

            # 物品栏
            inventory = game_state.get('inventory', [])
            if inventory:
                inv_text = '、'.join([f'{i["name"]}({i.get("type","misc")})' for i in inventory])
                user_prompt += f'\n当前物品栏：{inv_text}\n'

            # 状态效果
            conditions = game_state.get('conditions', [])
            if conditions:
                cond_text = '、'.join([f'{c["name"]}({c.get("type","neutral")}·剩余{c.get("duration","?")}回合)' for c in conditions])
                user_prompt += f'\n当前状态：{cond_text}\n'

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
                        parsed = self._parse_json_response(resp_content)
                        if parsed:
                            return parsed
                        last_error = f"JSON解析失败 (前500字): {resp_content[:500]}"
                        print(f"[LLM] {last_error}")
                    else:
                        err_msg = response.text[:200] if response.text else '无响应'
                        last_error = f"API错误 {response.status_code}: {err_msg}"
                        print(f"[LLM] {last_error}")
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

    def _is_llm_usable(self, override):
        """判断 LLM 是否可用：全局启用，或 override 带 key 且 (override.enabled 或全局 enabled)。"""
        if self.enabled:
            return True
        if not override:
            return False
        if not override.get('api_key', '').strip():
            return False
        return bool(override.get('enabled', False)) or self.enabled

    def generate_background(self, world, game_state, override=None):
        """生成身世介绍"""
        if not self._is_llm_usable(override):
            return None
        try:
            traits = game_state.get('traits', {})
            talents = game_state.get('talents', [])
            gender = game_state.get('gender', {}).get('name', '未知')
            race = game_state.get('race', {}).get('name', '未知')
            player_name = game_state.get('player_name', '')
            trait_text = '，'.join([f'{k}: {v}' for k, v in traits.items()])

            talent_text = '无'
            if talents:
                parts = []
                for t in talents:
                    effects = t.get('effect', {})
                    if effects:
                        eff_str = '，'.join([f'{k}+{v}' for k, v in effects.items()])
                        parts.append(f'{t["name"]}({eff_str})')
                    else:
                        parts.append(t['name'])
                talent_text = '，'.join(parts)

            system_prompt = """你是一个人生模拟游戏的叙事者。
根据玩家的天赋、属性和世界设定，生成一段身世介绍（150字左右）和该世界的初始世界书标签。
世界书标签规则：
- 标签自由分类，不必拘泥于固定维度，根据世界特色自行创建
- 每个分类下若干标签，标签取值范围 -10（极度负面）到 +10（极度正面），0 为中性
- 标签应反映世界核心特征
- 分类和标签数量不限，但总标签数建议在 8-15 个
要求：
- 身世要具有叙事感，像小说开头，结合天赋、属性和玩家期望的命运底色
- 始终用第二人称「你」称呼主角，不要用主角名替代「你」
- 世界书标签要准确反映世界特色，与描述高度一致
- 以JSON格式返回：{"background": "身世介绍", "world_tags": {"分类名": {"标签名": 数值}}}"""

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
                parsed = self._parse_json_response(content)
                if parsed:
                    # 验证必要字段
                    if 'background' not in parsed:
                        return {'_error': 'LLM 返回的 JSON 缺少 background 字段', '_raw': content[:500]}
                    return parsed
                return {'_error': 'LLM 返回内容不是有效的 JSON', '_raw': content[:500]}
            return {'_error': f'API 错误: {response.status_code}', '_status': response.status_code}
        except Exception as e:
            print(f"LLM background error: {e}")
            return {'_error': f'LLM 调用异常: {str(e)}', '_raw': ''}

    def generate_ending_evaluation(self, world, game_state, override=None):
        """生成人生总结评分"""
        if not self._is_llm_usable(override):
            return None
        try:
            traits = game_state.get('traits', {})
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

            # 新系统数据
            relationships = game_state.get('relationships', [])
            inventory = game_state.get('inventory', [])
            journal = game_state.get('journal', [])

            extra_text = ''
            if relationships:
                rel_text = '、'.join([f'{r["name"]}({r.get("relation","?")}·{r.get("status","中立")})' for r in relationships])
                extra_text += f'\n人物关系：{rel_text}\n'
            if inventory:
                inv_text = '、'.join([f'{i["name"]}' for i in inventory])
                extra_text += f'\n获得物品：{inv_text}\n'
            if journal:
                journal_text = '、'.join([f'{e.get("title","?")}' for e in journal[:10]])  # 最多10条
                extra_text += f'\n关键事件：{journal_text}\n'

            system_prompt = """你是一个人生评价者。请根据玩家的一生经历，给出客观评分和总结。
以JSON格式返回：
{"score": 85, "summary": "一生总结（100-200字，详细回顾人生亮点与遗憾）", "epitaph": "墓志铭/短评（30字内）", "title": "结局标题", "type": "good/normal/bad"}
评分规则（score 0-100）：寿命长短、经历丰富度、选择质量、人际关系、物品收集、综合命运。
type取值：good=好结局, normal=普通结局, bad=坏结局"""

            user_prompt = f"""世界设定：{world.get('name', '未知')}
性别：{gender}
种族：{race}
天赋：{talent_text}
属性：{trait_text}
{extra_text}

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
                parsed = self._parse_json_response(content)
                if parsed:
                    return parsed
                return {'_error': 'LLM 返回内容不是有效的 JSON', '_raw': content[:500]}
            return {'_error': f'API 错误: {response.status_code}', '_status': response.status_code}
        except Exception as e:
            print(f"LLM ending error: {e}")
            return {'_error': f'LLM 调用异常: {str(e)}', '_raw': ''}



    def generate_image(self, world, game_state, ending, override=None):
        """生成四格漫画图像，返回图片路径或错误"""
        img_cfg = load_image_gen_config()
        # session override 的生图配置优先
        if override:
            if override.get('image_gen_api_base'):
                img_cfg['api_base'] = override['image_gen_api_base']
            if override.get('image_gen_api_key'):
                img_cfg['api_key'] = override['image_gen_api_key']
            if override.get('image_gen_model'):
                img_cfg['model'] = override['image_gen_model']
            if override.get('image_gen_size'):
                img_cfg['size'] = override['image_gen_size']
        if not img_cfg.get('enabled') or not img_cfg.get('api_key'):
            return {'_error': '生图功能未启用或未配置 API Key'}

        history = game_state.get('history', [])
        if not history:
            return {'_error': '没有游玩记录'}

        # 构建人生经历文本
        history_text = ''
        for record in history:
            year = record.get('year', '?')
            event = record.get('event', '')
            choice = record.get('choice', '')
            history_text += f"{year}岁: {event}"
            if choice:
                history_text += f" (选择: {choice})"
            history_text += '\n'

        # 让 LLM 生成详细的四格漫画提示词
        comic_prompt_text = self._build_comic_prompt(world, game_state, ending, history_text, override)
        if isinstance(comic_prompt_text, dict) and '_error' in comic_prompt_text:
            return comic_prompt_text

        # 调用生图 API
        try:
            from pathlib import Path
            import time

            api_base = img_cfg['api_base'].rstrip('/')
            response = requests.post(
                f"{api_base}/images/generations",
                headers={
                    'Authorization': f"Bearer {img_cfg['api_key']}",
                    'Content-Type': 'application/json',
                },
                json={
                    'model': img_cfg['model'],
                    'prompt': comic_prompt_text,
                    'n': 1,
                    'size': img_cfg['size'],
                    'quality': img_cfg['quality'],
                    'style': img_cfg['style'],
                },
                timeout=3600
            )

            if response.status_code != 200:
                detail = f'模型: {img_cfg["model"]}\n尺寸: {img_cfg["size"]}\nAPI: {img_cfg["api_base"]}\nHTTP {response.status_code}: {response.text[:500]}'
                return {'_error': f'生图 API 错误: {response.status_code}', '_trace': detail, '_raw': response.text[:500]}

            data = response.json()
            image_url = data['data'][0]['url']

            # 下载图片并保存到本地
            img_response = requests.get(image_url, timeout=300)
            if img_response.status_code != 200:
                return {'_error': '下载图片失败', 'url': image_url}

            img_dir = Path(__file__).parent / 'static' / 'generated'
            img_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            img_filename = f"life_comic_{timestamp}.png"
            img_path = img_dir / img_filename
            with open(img_path, 'wb') as f:
                f.write(img_response.content)

            return {
                'status': 'ok',
                'url': f'/static/generated/{img_filename}',
                'prompt': comic_prompt_text
            }
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f'[ImageGen] 生图异常: {e}')
            print(tb)
            return {'_error': f'生图异常: {str(e)}', '_trace': tb}

    def _build_comic_prompt(self, world, game_state, ending, history_text, override=None):
        """让 LLM 构建详细的四格漫画生图提示词"""
        build_prompt = f"""你是一个专业的漫画分镜师。根据以下人生经历，构建一个详细的四格漫画生图提示词。

世界设定：{world.get('name', '未知')} - {world.get('description', '')}
身世背景：{game_state.get('background', '无')}
结局：{ending.get('title', '')} - {ending.get('text', '')}
结局类型：{ending.get('type', 'normal')}

完整人生经历：
{history_text}

请构建一个详细的四格漫画生图提示词（中文），要求：
1. 格式：四格漫画，方形（1:1），2x2网格布局
2. 风格：根据世界设定和结局类型选择合适的艺术风格（如黑暗奇幻、明亮童话、科幻、武侠水墨等）
3. 主角：根据玩家性别、种族、天赋设计统一的主角形象，每格保持一致性
4. 四格内容：
   - 第一格：天赋/起点/童年
   - 第二格：关键转折/最大挑战
   - 第三格：高潮/命运抉择
   - 第四格：结局/终局场景
5. 每格包含：场景描述、角色动作、光影氛围、色调、对话或旁白（用对话气泡或旁白框显示）
6. 整体色调：根据故事走向设计色调变化（如从明亮到黑暗，或从黑暗到光明）
7. 文字要求：所有对话和旁白必须清晰显示在矩形旁白框或白色对话气泡中

直接输出完整的中文提示词，不要解释。"""

        messages = [
            {'role': 'system', 'content': '你是一个专业的漫画分镜师，擅长为生图AI构建详细的提示词。'},
            {'role': 'user', 'content': build_prompt}
        ]

        try:
            response = self._make_request(messages, override)
            if response.status_code != 200:
                return {'_error': f'LLM 构建提示词失败: {response.status_code}'}
            result = response.json()
            prompt_text = result['choices'][0]['message']['content'].strip()
            return prompt_text
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f'[ImageGen] 构建提示词异常: {e}')
            print(tb)
            return {'_error': f'构建提示词异常: {str(e)}', '_trace': tb}

def load_image_gen_config():
    """加载生图配置（合并环境变量）"""
    config = load_config().get('image_gen', {})
    env_config = {
        'enabled': os.environ.get('IMAGE_GEN_ENABLED', None),
        'api_base': os.environ.get('IMAGE_GEN_API_BASE', None),
        'api_key': os.environ.get('IMAGE_GEN_API_KEY', None),
        'model': os.environ.get('IMAGE_GEN_MODEL', None),
        'size': os.environ.get('IMAGE_GEN_SIZE', None),
        'quality': os.environ.get('IMAGE_GEN_QUALITY', None),
        'style': os.environ.get('IMAGE_GEN_STYLE', None),
    }
    for key, value in env_config.items():
        if value is not None:
            if key == 'enabled':
                config[key] = value.lower() == 'true'
            else:
                config[key] = value
    config.setdefault('enabled', False)
    config.setdefault('api_base', 'https://api.openai.com/v1')
    config.setdefault('api_key', '')
    config.setdefault('model', 'dall-e-3')
    config.setdefault('size', '1024x1024')
    config.setdefault('quality', 'standard')
    config.setdefault('style', 'vivid')
    return config
