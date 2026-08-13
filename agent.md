# AI 人生重开手帐 — 面向编程 Agent 的项目说明

> 本文档的目标不是写给普通玩家，而是让另一个 AI/编程 Agent 在读完本文后，能够快速理解项目的整体结构、请求链路、状态模型、前后端路由，以及修改某个功能时应该去哪些文件定位。

## 1. 项目一句话概括

这是一个单进程 **Flask + 纯前端 HTML/CSS/JS** 的互动文字人生模拟游戏。玩家选择预设或 AI 随机世界，设定身份、抽天赋、分配属性，然后由服务端调用兼容 OpenAI Chat Completions 的 LLM，按批次生成人生事件、选项、属性变化、世界标签变化、人物关系、物品、状态和事件日志；结局时再调用 LLM 评分，并可异步调用生图 API 生成“人生四格漫画”。

服务端不接数据库，主要状态存在：

- Flask 服务端会话：`.sessions/`
- 公开游戏记录：`records/*.json`
- 生图结果：`static/generated/*.jpg`
- 浏览器短期设置：`sessionStorage`
- 浏览器多槽位存档：`localStorage`

## 2. 技术栈

- 语言：Python 3
- Web 框架：Flask
- 会话：Flask-Session，filesystem 后端
- HTTP 客户端：requests
- 图片处理：Pillow
- 前端：原生 Jinja2 模板 + 原生 HTML/CSS/JavaScript，无前端框架
- 导出图片：浏览器端按需加载 `html2canvas`
- LLM：兼容 OpenAI 格式的 `/chat/completions`
- 生图：兼容 OpenAI 格式的 `/images/generations`

## 3. 目录与文件职责

| 路径 | 作用 |
|---|---|
| `app.py` | Flask 应用入口、配置加载、会话、蓝图注册、配置热重载、启动 |
| `routes/__init__.py` | 把 `pages_bp` 和 `api_bp` 注册到 app |
| `routes/pages.py` | 页面路由，主要负责返回 Jinja 模板和推进“建号流程” |
| `routes/api.py` | JSON API 路由，负责 LLM 事件生成、选择、存档、记录、设置、生图任务 |
| `llm_client.py` | OpenAI 格式 API 客户端、Prompt 构造、事件/身世/结局/生图提示词生成 |
| `game_data.py` | 静态游戏数据：属性图标与描述、天赋、性别、种族、预设世界、世界默认标签 |
| `game_utils.py` | 游戏业务函数：抽天赋、应用天赋、世界查找、审核、记录读写、会话清理 |
| `world_tags.py` | 世界书标签的读取、合并、清理、格式化 |
| `templates/` | Jinja 页面模板 |
| `static/` | 背景音乐、图标、主题曲页面、运行时生成的漫画 |
| `records/` | 运行时生成并保存的公开/隐藏游戏记录 JSON |
| `.sessions/` | Flask-Session 的服务端会话文件 |
| `config.json` | 运行时配置，支持热重载；默认被 `.gitignore` 排除 |
| `Dockerfile` | 容器化启动 |

## 4. 后端启动流程

入口在 `app.py`：

1. 创建 `.sessions` 目录。
2. `RAW_CONFIG = load_config()` 读取并补全 `config.json`。
3. `LLM_CONFIG = merge_config()` 读取 LLM 配置并合并环境变量。
4. 创建 Flask app，设置 secret key 与 Flask-Session：
   - `SESSION_TYPE = 'filesystem'`
   - 会话生命周期 3 小时。
5. 注册 Jinja 全局函数：
   - `get_trait_icon`
   - `get_trait_desc`
   - `url_for_static`
6. 创建全局 `LLMClient`，并存到 `app.llm_client` / `app.LLM_CONFIG`，供 blueprint 通过 `current_app` 使用。
7. 注册 `before_request`：非 `/static/` 请求会检查 `config.json` 的 mtime，发生变化时重新加载 LLM 配置。
8. `register_blueprints(app)` 注册页面和 API 蓝图。
9. `app.run` 按 `config.json -> app.port/debug` 启动。

关键位置：

- 会话初始化：`app.py:26`
- 配置加载：`app.py:30`
- LLM 配置合并：`app.py:32`
- Flask app / secret key：`app.py:34`
- Session 初始化：`app.py:45`
- Jinja 全局函数：`app.py:49`
- context processor：`app.py:53`
- LLM 客户端挂载：`app.py:60`
- 热重载：`app.py:72`
- before_request：`app.py:98`
- 蓝图注册：`app.py:108`
- 蓝图注册函数：`routes/__init__.py:10`

### 4.1 配置优先级

LLM 配置由 `config.json` 与环境变量合并，环境变量优先：

- `LLM_ENABLED`
- `LLM_API_BASE`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`
- `LLM_CUSTOM_BODY`

生图配置见 `llm_client.py:847`：

- `IMAGE_GEN_ENABLED`
- `IMAGE_GEN_API_BASE`
- `IMAGE_GEN_API_KEY`
- `IMAGE_GEN_MODEL`
- `IMAGE_GEN_SIZE`
- `IMAGE_GEN_QUALITY`
- `IMAGE_GEN_STYLE`

## 5. 核心数据模型

### 5.1 服务端 Flask session

主要 session key：

| key | 含义 |
|---|---|
| `session['game']` | 当前一局游戏的完整状态，详见下文 |
| `session['custom_world']` | 自定义世界或 LLM 随机世界的世界对象 |
| `session['llm_override']` | 前端设置面板提交的用户级 LLM 覆盖配置 |
| `session['entry_origin']` | 简单流程闸门，防止直接访问游戏页；首页和记录页等会设置 |

`session['game']` 在流程中逐渐填充，关键字段包括：

| 字段 | 含义 |
|---|---|
| `world_id` | 当前世界 id |
| `world_name` | 随机/自定义世界名，主要用于存档 |
| `custom_world` | 随机/自定义世界对象 |
| `gender` | 性别对象 |
| `race` | 种族对象 |
| `custom_race` / `custom_race_desc` | 自定义种族 |
| `custom_destiny` | 玩家填写的命运底色 |
| `player_name` | 玩家名，最长 12 字 |
| `show_record` | 是否公开记录 |
| `talents` | 选中的天赋列表 |
| `trait_pool` | 当前抽出的天赋池 |
| `rerolls_left` | 天赋重抽次数 |
| `traits` | 最终属性 dict，如 `{"力量": 5}` |
| `background` | 身世文本 |
| `history` | 已发生的人生事件列表 |
| `current_year` | 当前年份/周 |
| `step` | 流程状态机状态 |
| `pending_choices` | 待玩家选择的选择列表 |
| `last_choice` | 上一次选择文本 |
| `world_tags` | 世界书标签 dict |
| `relationships` | 人物关系列表 |
| `inventory` | 物品栏 |
| `conditions` | 状态效果 |
| `journal` | 关键事件日志 |
| `ending` | 结局对象 |
| `generated_image` | 生图 URL |
| `record_filename` | 保存记录后写入的文件名，供生图回写 |

### 5.2 `step` 状态机

页面后端通过 `session['game']['step']` 控制允许访问的页面和 API：

| step | 位置/含义 |
|---|---|
| `not_started` | `POST /game/<world_id>/start` 创建 |
| `identity_done` | 完成身份设定 |
| `talents_done` | 完成天赋抽取 |
| `traits_done` | 完成属性分配 |
| `playing` | 命运预览页 POST 后进入游戏 |
| `ended` | `/next` 判定人生结束 |

### 5.3 `history` 元素结构

每个历史事件在 `routes/api.py` 中写入：

```json
{
  "year": 1,
  "event": "事件文本",
  "choice": null,
  "trait_changes": {"力量": -1},
  "world_tag_changes": {"社会结构": {"政治稳定": 1}},
  "age_icon": "👶"
}
```

### 5.4 `world_tags` 结构

世界标签是“分类 -> 标签 -> 数值”的嵌套 dict：

```json
{
  "社会结构": {"政治稳定": -5, "法治程度": 4},
  "超自然": {"超自然强度": 8}
}
```

合并规则见 `world_tags.py:23`，支持：

- 点号扁平格式：`{"社会结构.政治稳定": 2}`
- 嵌套格式：`{"社会结构": {"政治稳定": 2}}`
- 简单标量格式：`{"新分类名": 5}`
- `null` 表示删除

## 6. 后端页面路由（`routes/pages.py`）

所有路径与处理函数如下：

| Method | Path | Handler | 代码位置 | 返回/作用 |
|---|---|---|---|---|
| GET | `/` | `index` | `routes/pages.py:29` | 首页，渲染 `index.html`，传入 `worlds=WORLDS` |
| GET | `/custom` | `custom_world` | `routes/pages.py:36` | 自定义世界创建页 `custom.html` |
| GET | `/world/random` | `random_world_detail` | `routes/pages.py:43` | 展示 session 中的随机世界 `world.html` |
| GET | `/world/<world_id>` | `world_detail` | `routes/pages.py:53` | 世界详情；`blue_archive` 返回章节选择页，其余返回 `world.html` |
| GET/POST | `/game/custom/identity` | `custom_game_identity` | `routes/pages.py:67` | 自定义世界的身份设定；GET 用 query 参数构造世界 |
| GET/POST | `/game/<world_id>/quickstart` | `game_quickstart` | `routes/pages.py:112` | 蔚蓝档案章节的“跳过天赋/身份”快速开局，GET 渲染 `traits.html` |
| POST | `/game/<world_id>/start` | `game_start` | `routes/pages.py:142` | 初始化普通世界游戏，返回下一步 URL |
| POST | `/game/random/start` | `game_random_start` | `routes/pages.py:164` | 初始化随机世界游戏 |
| GET/POST | `/game/<world_id>/identity` | `game_identity` | `routes/pages.py:186` | 身份设定页，POST 保存身份 |
| GET/POST | `/game/<world_id>/talents` | `game_talents` | `routes/pages.py:216` | 天赋抽取页，POST 抽卡/重抽/确认 |
| GET/POST | `/game/<world_id>/traits` | `game_traits` | `routes/pages.py:250` | 属性分配页，POST 保存属性 |
| GET/POST | `/game/<world_id>/preview` | `game_preview` | `routes/pages.py:271` | 命运预览，GET 生成身世，POST 进入游戏 |
| GET | `/game/<world_id>/play` | `game_play` | `routes/pages.py:333` | 游戏主页面 |
| GET | `/game/<world_id>/ending` | `game_ending` | `routes/pages.py:351` | 结局页 |
| GET | `/game/export` | `export_record` | `routes/pages.py:382` | 导出当前人生记录 JSON 数据，前端再生成 txt/json 下载 |
| GET | `/records` | `records_page` | `routes/pages.py:504` | 公开记录页 |
| GET | `/about` | `about` | `routes/pages.py:511` | 关于页 |

### 6.0.1 页面路由内部辅助函数

| 函数 | 代码位置 | 作用 |
|---|---|---|
| `_get_llm_client` | `routes/pages.py:19` | 从 `current_app` 取 LLM 客户端 |
| `_get_llm_config` | `routes/pages.py:23` | 从 `current_app` 取 LLM 配置 |

### 6.1 建号流程（普通世界）

1. 首页 `/` 点击世界卡片 → GET `/world/<world_id>`。
2. 前端 `world.html` 输入玩家名/公开开关 → POST `/game/<world_id>/start`。
3. 后端创建 `session['game']`，返回 `next_step=/game/<world_id>/identity`。
4. `identity.html` POST 到同一 URL，保存性别、种族、命运，返回 talents。
5. `talents.html` 对同一 URL 发送三种 action：
   - `draw`：抽 3 天赋
   - `reroll`：重抽
   - `confirm`：确认选择
6. `traits.html` POST 属性 dict，后端调用 `apply_talents_to_traits`。
7. `preview.html` GET 会触发 `LLMClient.generate_background`；POST 则设置 `step=playing`。
8. 进入 `game.html`。

### 6.2 自定义世界流程

1. GET `/custom`。
2. `custom.html` 把名称、描述、四个属性拼成 query 参数，跳转 `/game/custom/identity?name=...&desc=...&traits=...`。
3. `custom_game_identity` GET 在 session 中构造 `custom_world`，再走 identity → talents → traits → preview → play。

### 6.3 蔚蓝档案章节流程

`/world/blue_archive` 特殊返回 `blue_archive.html`。玩家选择：

- `/world/blue_archive_abydos`
- `/world/blue_archive_gamedev`

这两个世界的 `parent` 字段为 `blue_archive`，`time_unit` 为 `周`，`ending_type` 为 `mission`。它们从 `/game/<world_id>/start` 跳转到 `/game/<world_id>/quickstart`，然后直接进入属性分配和游戏。

## 7. 后端 API 路由（`routes/api.py`）

### 7.1 路由总表

| Method | Path | Handler | 代码位置 | 作用 |
|---|---|---|---|---|
| POST | `/api/random-world` | `api_random_world` | `routes/api.py:59` | 调用 LLM 生成随机世界并写入 session |
| POST | `/game/<world_id>/next` | `game_next` | `routes/api.py:130` | 调用 LLM 生成下一批事件/选项/结局 |
| POST | `/game/<world_id>/choose` | `game_choose` | `routes/api.py:355` | 保存玩家选择到最后一个历史事件 |
| GET | `/game/save` | `save_game` | `routes/api.py:390` | 从 session 导出当前存档 JSON |
| POST | `/game/load` | `load_game` | `routes/api.py:427` | 从上传文件恢复存档 |
| POST | `/game/load-json` | `load_game_json` | `routes/api.py:462` | 从请求 JSON 恢复存档 |
| POST | `/api/llm-config` | `api_llm_config` | `routes/api.py:495` | 将前端设置面板内容写入 session override |
| GET | `/api/records` | `api_records` | `routes/api.py:555` | 列出公开记录元信息 |
| GET | `/api/records/<path:filename>` | `api_record_detail` | `routes/api.py:564` | 读取单条记录完整 JSON |
| POST | `/api/generate-image` | `api_generate_image` | `routes/api.py:629` | 启动异步生图任务 |
| GET | `/api/generate-image/status/<task_id>` | `api_generate_image_status` | `routes/api.py:665` | 轮询生图任务状态 |

### 7.1.1 API 内部辅助函数

| 函数 | 代码位置 | 作用 |
|---|---|---|
| `_filter_zero_changes` | `routes/api.py:28` | 过滤值为 0 的世界标签变化 |
| `_get_llm_client` | `routes/api.py:48` | 从 `current_app` 取 LLM 客户端 |
| `_get_llm_config` | `routes/api.py:53` | 从 `current_app` 取 LLM 配置 |
| `_do_generate_image` | `routes/api.py:584` | 后台线程执行生图任务 |

### 7.2 `/api/random-world` — `routes/api.py:59`

- 请求：无 body。
- 成功返回：`{"status":"ok","world":{...}}`。
- 生成的世界被写入 `session['custom_world']`。
- LLM 返回需要解析出 `name/icon/description/color/traits/preview/prompt`。

### 7.3 `/game/<world_id>/next` — `routes/api.py:130`

这是游戏核心 API。它执行：

1. 校验世界已解锁、`session['game']['step'] == 'playing'`。
2. 判断 LLM 是否可用：全局配置或 session override。
3. 调用 `LLMClient.generate_events_batch(world, game, override)`。
4. 解析并合并：
   - `trait_changes`
   - `world_tag_changes`
   - `relationship_changes`
   - `inventory_changes`
   - `condition_changes`
   - `journal_entries`
5. 根据 `finished` 判断是否结束。
6. 如果结束，调用 `generate_ending_evaluation`，再 `save_game_record`。
7. 返回完整状态。

`game_next` 内部各阶段位置：

| 阶段 | 代码位置 |
|---|---|
| 调用 LLM 并标准化事件 | `routes/api.py:148-190` |
| 合并世界标签变化 | `routes/api.py:191-202` |
| 合并人物关系变化 | `routes/api.py:204-229` |
| 合并物品栏变化 | `routes/api.py:231-247` |
| 合并状态效果变化 | `routes/api.py:249-269` |
| 追加事件日志 | `routes/api.py:271-283` |
| 写入 history、current_year、属性 | `routes/api.py:295-311` |
| 结局评价与保存记录 | `routes/api.py:313-334` |
| 组装 API 响应 | `routes/api.py:336-351` |

成功响应字段：

```json
{
  "events": [],
  "choices": [],
  "ended": false,
  "llm_error": null,
  "retry": false,
  "fortune": 50,
  "world_tags": {},
  "relationships": [],
  "inventory": [],
  "conditions": [],
  "journal": [],
  "relationship_changes": [],
  "inventory_changes": [],
  "condition_changes": [],
  "journal_entries": [],
  "record_saved": true,
  "record_message": ""
}
```

事件字段：

```json
{
  "year": 1,
  "event": "文本",
  "age_icon": "👶",
  "trait_changes": {},
  "world_tag_changes": {}
}
```

### 7.4 `/game/<world_id>/choose` — `routes/api.py:355`

- 请求 body：

```json
{
  "choice": 0,
  "custom_text": "可选，当 choice=3 时使用"
}
```

- 服务端根据 `pending_choices` 取得选择文本，写入最后一个 `history` 项的 `choice`，清空 `pending_choices`。
- 返回 `{"status":"ok"}`。

### 7.5 存档相关

`GET /game/save`（`routes/api.py:390`）：

- 从 `session['game']` 生成 `version=1` 的存档 JSON。
- 若最后一段历史未选择，会包含 `pending_choices`。

`POST /game/load`（`routes/api.py:427`）：

- 接收 `multipart/form-data` 的 `file` 字段。
- 校验 `version==1`，写入 session，并跳转到 `/game/<world_id>/play`。

`POST /game/load-json`（`routes/api.py:462`）：

- 接收原始 JSON，用于前端 localStorage 存档恢复和 `importSaveFile`。

### 7.6 `/api/llm-config` — `routes/api.py:495`

- 前端设置面板调用。
- 写入 `session['llm_override']`。
- `enabled` 只有在用户填了 `api_key` 时才为 true。
- 同时接收：
  - LLM：`api_base/api_key/model/temperature/top_p/max_tokens/batch_min/batch_max/event_words/writing_style/json_mode/custom_body/use_journal`
  - 生图：`image_gen_api_base/image_gen_api_key/image_gen_model/image_gen_size`

### 7.7 公开记录

`GET /api/records`（`routes/api.py:555`）：

- 读取 `records/*.json`。
- 跳过文件名含 `nodisplay` 的记录。
- 缓存列表，目录 mtime 不变时复用。
- 返回元信息数组：

```json
[
  {
    "filename": "...json",
    "world": "世界名",
    "player_name": "",
    "lifespan": 10,
    "score": 85,
    "saved_at": "ISO 时间",
    "title": "结局标题"
  }
]
```

`GET /api/records/<path:filename>`（`routes/api.py:564`）：

- 有路径穿越防护，解析后的路径必须仍在 `records/` 下。
- 返回该记录完整 JSON。

### 7.8 生图异步任务

`POST /api/generate-image`（`routes/api.py:629`）：

1. 校验 `session['game']` 和 `history` 存在。
2. 创建 `uuid` task id，写入内存 `_image_tasks`。
3. 用 `ThreadPoolExecutor(max_workers=2)` 后台执行 `_do_generate_image`。
4. 立即返回 `{"task_id":"...","status":"pending"}`。

后台任务：

1. 调用 `LLMClient.generate_image`。
2. 生图成功后：
   - 把 URL 写回 `session['game']['generated_image']`
   - 如果 `record_filename` 存在，调用 `update_record_image`
3. 更新 `_image_tasks[task_id]` 状态。

状态接口（`routes/api.py:665`）：

```json
{
  "status": "pending|processing|ok|error",
  "progress": "...",
  "result": {}
}
```

## 8. LLM 客户端（`llm_client.py`）

### 8.1 配置与请求

相关函数位置：

| 函数 | 代码位置 | 作用 |
|---|---|---|
| `ensure_config` | `llm_client.py:20` | 补全并写回 `config.json` |
| `load_config` | `llm_client.py:83` | 读取配置文件 |
| `merge_config` | `llm_client.py:88` | 合并 LLM 环境变量 |
| `LLMClient.__init__` | `llm_client.py:135` | 初始化客户端，判定 `enabled` |
| `_make_request` | `llm_client.py:140` | 实际发送 `/chat/completions` 请求 |

`LLMClient.__init__` 的 `enabled` 条件：

```python
config['enabled'] and config['api_key'] and HAS_REQUESTS
```

`_make_request(messages, override)`：

- 若 session override 有 `api_key` 且（`override.enabled` 或全局 enabled），则使用 override。
- URL 固定拼接：`{api_base}/chat/completions`。
- 请求体包含：
  - `model`
  - `messages`
  - `temperature`
  - `max_tokens`
  - 可选 `top_p`
  - 可选 `response_format={"type":"json_object"}`
  - `custom_request_body` 合并
- 超时时间 `3600` 秒。

### 8.2 LLM 能力

| 方法 | 位置 | 作用 |
|---|---|---|
| `generate_events_batch` | `llm_client.py:210` | 生成一批事件 + 3 个选择 + 所有新系统变化 |
| `generate_background` | `llm_client.py:522` | 生成身世和初始世界标签 |
| `generate_ending_evaluation` | `llm_client.py:589` | 生成结局评分、总结、标题、类型 |
| `generate_image` | `llm_client.py:666` | 先让 LLM 构造四格漫画提示词，再调用生图 API |
| `_build_comic_prompt` | `llm_client.py:794` | 构造漫画分镜提示词 |
| `_parse_json_response` | `llm_client.py:193` | 从 LLM 文本提取 JSON |
| `_is_llm_usable` | `llm_client.py:512` | 判断当前请求是否可用 LLM |

### 8.3 事件生成 Prompt 结构

`generate_events_batch` 的系统提示词包含：

- 世界设定 `world.prompt`
- 世界书 `format_world_tags(world_tags)`
- 核心叙事规则
- 选择设计规则
- 结局机制
- 运势值
- 世界书标签变化规则
- 人物关系系统
- 物品栏系统
- 状态效果系统
- 事件日志系统
- 严格 JSON 输出格式

要求 LLM 返回的字段：

```json
{
  "events": [],
  "choices": [],
  "world_tag_changes": {},
  "relationship_changes": [],
  "inventory_changes": [],
  "condition_changes": [],
  "journal_entries": [],
  "finished": "false|true|fail",
  "fortune": 50,
  "epitaph": ""
}
```

用户提示词会包含：

- 世界、性别、种族、天赋、属性、当前进度、命运底色
- 当前人物关系、物品、状态
- 完整人生历史（或 `use_journal` 开启时的关键事件摘要 + 最近 3 轮）

### 8.4 生图流程

相关函数：

| 函数 | 代码位置 | 作用 |
|---|---|---|
| `generate_image` | `llm_client.py:666` | 生图主流程 |
| `_build_comic_prompt` | `llm_client.py:794` | 构造四格漫画提示词 |
| `load_image_gen_config` | `llm_client.py:847` | 读取并合并生图环境变量 |
| `_convert_image_bytes_to_jpeg` | `llm_client.py:875` | 统一转换图片为 JPEG |

`generate_image` 的执行流程：

1. 读取 `load_image_gen_config()`。
2. session override 的生图配置优先。
3. 用 `_build_comic_prompt` 生成中文提示词。
4. POST `{image_api_base}/images/generations`。
5. 支持 API 返回 `b64_json` 或 `url`。
6. 下载并交给 `_convert_image_bytes_to_jpeg` 转 JPEG，质量 85。
7. 保存到 `static/generated/life_comic_<timestamp>.jpg`。
8. 返回 `url=/static/generated/...`。

## 9. 游戏工具与静态数据

### 9.1 `game_data.py`

- `TRAIT_ICONS`：属性名到 emoji，见 `game_data.py:8`
- `TRAIT_DESCS`：属性名到说明，见 `game_data.py:19`
- `TALENTS`：天赋池，含 `id/name/description/rarity/effect/color/negative`，见 `game_data.py:71`
- `GENDERS`：性别选项，见 `game_data.py:93`
- `RACES`：种族选项，见 `game_data.py:100`
- `WORLDS`：所有预设世界，见 `game_data.py:109`
- `WORLD_TAG_DEFAULTS`：世界默认标签，见 `game_data.py:177`
- `get_trait_icon`：`game_data.py:59`
- `get_trait_desc`：`game_data.py:64`

预设世界：

| id | 名称 | 特殊字段 |
|---|---|---|
| `warhammer40k` | 战锤 40K | 无 |
| `blue_archive` | 蔚蓝档案 | `chapter_select=True` |
| `blue_archive_abydos` | 阿拜多斯篇 | `hidden=True`, `parent`, `time_unit='周'`, `ending_type='mission'` |
| `blue_archive_gamedev` | 游戏开发部篇 | 同上 |
| `arknights` | 明日方舟 | 无 |
| `harry_potter` | 魔法世界 | 无 |
| `wuxia` | 武侠江湖 | 无 |
| `wasteland` | 末日废土 | 无 |

### 9.2 `game_utils.py`

| 函数 | 位置 | 作用 |
|---|---|---|
| `draw_talents` | `game_utils.py:17` | 按稀有度概率抽取天赋 |
| `apply_talents_to_traits` | `game_utils.py:41` | 把天赋加成应用到属性 |
| `check_entry` | `game_utils.py:50` | 检查是否从首页入口进入 |
| `get_age_icon` | `game_utils.py:55` | 按年龄返回 emoji |
| `get_world` | `game_utils.py:71` | 从 `WORLDS` 或 session 获取世界 |
| `moderate_content_text` | `game_utils.py:86` | 调用 LLM 审核内容 |
| `get_records_list` | `game_utils.py:128` | 列出公开记录，带目录 mtime 缓存 |
| `save_game_record` | `game_utils.py:157` | 审核后写入 `records/*.json` |
| `update_record_image` | `game_utils.py:251` | 生图后回写记录 JSON |
| `cleanup_old_sessions` | `game_utils.py:272` | 清理 24 小时前的 session |

### 9.3 `world_tags.py`

见第 5.4 节。相关函数位置：

| 函数 | 代码位置 | 作用 |
|---|---|---|
| `get_world_tags` | `world_tags.py:11` | 读取预设标签副本 |
| `_merge_world_tag_changes` | `world_tags.py:23` | 合并 LLM 返回的变化 |
| `_clean_world_tags` | `world_tags.py:99` | 移除 null 值和空分类 |
| `format_world_tags` | `world_tags.py:114` | 把标签转为可拼进 Prompt 的文本 |

## 10. 前端结构与模板继承

所有主页面继承 `templates/base.html`。

`base.html` 提供：

- 全局 CSS 变量、明暗主题、世界主题皮肤
- 背景音乐按钮和 `bgm.mp3`
- 深色模式按钮
- LLM 设置浮层
- 页面加载动画、Toast、按钮涟漪、滚动入场动画
- 底部的 `block scripts` 占位

模板可以覆盖的 block：

- `title`
- `meta`
- `extra_styles`
- `body_attrs`
- `content`
- `scripts`

### 10.1 页面模板与关键前端脚本

| 模板 | 主要职责 | 关键脚本行 |
|---|---|---|
| `templates/index.html` | 世界列表、随机世界、导入存档 | `index.html:283` |
| `templates/custom.html` | 自定义世界表单 | `custom.html:52` |
| `templates/world.html` | 世界详情，开始世界 | `world.html:127` |
| `templates/blue_archive.html` | 蔚蓝档案章节选择 | 无 JS |
| `templates/identity.html` | 性别/种族/命运设定 | `identity.html:288` |
| `templates/talents.html` | 抽卡、重抽、确认 | `talents.html:549` |
| `templates/traits.html` | 属性分配，Konami 无限模式 | `traits.html:298` |
| `templates/preview.html` | 身世和世界书预览，开始游戏 | `preview.html:363` |
| `templates/game.html` | 核心游戏循环、系统面板、存档管理 | `game.html:1038` |
| `templates/ending.html` | 结局、生图、导出 | `ending.html:355` |
| `templates/records.html` | 公开记录列表与详情 | `records.html:74` |
| `templates/about.html` | 关于页 | 无 JS |
| `templates/error.html` | 错误页 | 无 JS |

### 10.1.1 前端主要函数定位

| 功能 | 函数 | 代码位置 |
|---|---|---|
| 首页装饰粒子 | `initParticles` | `templates/index.html:285` |
| 随机世界生成 | `randomWorld` | `templates/index.html:302` |
| 首页导入存档 | `loadGame` | `templates/index.html:325` |
| 创建自定义世界并跳转 | `startCustomWorld` | `templates/custom.html:53` |
| 世界详情页开始游戏 | `startJourney` | `templates/world.html:130` |
| 身份：选择性别 | `selectGender` | `templates/identity.html:292` |
| 身份：选择种族 | `selectRace` | `templates/identity.html:298` |
| 身份：自定义种族输入 | `onCustomRaceInput` | `templates/identity.html:307` |
| 身份：更新选中态 | `updateSelection` | `templates/identity.html:319` |
| 身份：控制下一步按钮 | `checkNextButton` | `templates/identity.html:329` |
| 身份：提交身份设定 | `confirmIdentity` | `templates/identity.html:335` |
| 身份页初始化 | DOMContentLoaded | `templates/identity.html:365` |
| 天赋：抽卡 | `drawTalents` | `templates/talents.html:555` |
| 天赋：重抽 | `rerollTalents` | `templates/talents.html:582` |
| 天赋：展示抽卡结果 | `showTalents` | `templates/talents.html:601` |
| 天赋：选中/取消 | `toggleTalent` | `templates/talents.html:691` |
| 天赋：按钮状态 | `updateButtons` | `templates/talents.html:703` |
| 天赋：稀有度文本 | `getRarityText` | `templates/talents.html:708` |
| 天赋：粒子动画 | `createParticleBurst` | `templates/talents.html:719` |
| 天赋：传说卡金粉 | `startGoldDust` | `templates/talents.html:760` |
| 天赋：确认选择 | `confirmTalents` | `templates/talents.html:786` |
| 属性：增减属性 | `changeValue` | `templates/traits.html:308` |
| 属性：刷新显示 | `updateDisplay` | `templates/traits.html:320` |
| 属性：无限模式快捷键 | DOM keydown | `templates/traits.html:337` |
| 属性：提交属性 | `confirmTraits` | `templates/traits.html:352` |
| 预览：展开世界书 | `toggleWorldBook` | `templates/preview.html:364` |
| 预览：开始人生 | `startGame` | `templates/preview.html:371` |
| 游戏：合并同一年事件 | `mergePastEvents` | `templates/game.html:875` |
| 游戏：运势边框颜色 | `updateFortuneBorder` | `templates/game.html:1044` |
| 游戏：恢复待处理选项 | `initPendingChoices` | `templates/game.html:1064` |
| 游戏：更新年龄 | `updateAgeDisplay` | `templates/game.html:1076` |
| 游戏：属性颜色 | `updateTraitColor` | `templates/game.html:1084` |
| 游戏：属性变化动画 | `updateHeaderTraits` | `templates/game.html:1090` |
| 游戏：新增事件卡片 | `addEvent` | `templates/game.html:1110` |
| 游戏：显示选项 | `showChoices` | `templates/game.html:1198` |
| 游戏：显示继续按钮 | `showStartButton` | `templates/game.html:1219` |
| 游戏：显示重试按钮 | `showRetryButton` | `templates/game.html:1229` |
| 游戏：显示结局按钮 | `showEnding` | `templates/game.html:1243` |
| 游戏：请求下一批事件 | `continueLife` | `templates/game.html:1253` |
| 游戏：展示单个事件 | `showNextEvent` | `templates/game.html:1333` |
| 游戏：展示下一年按钮 | `showNextYearButton` | `templates/game.html:1351` |
| 游戏：点击预设选择 | `makeChoice` | `templates/game.html:1363` |
| 游戏：提交自定义选择 | `makeCustomChoice` | `templates/game.html:1370` |
| 游戏：提交选择到后端 | `submitChoice` | `templates/game.html:1384` |
| 游戏：世界书弹窗 | `toggleWorldBook` | `templates/game.html:1429` |
| 游戏：渲染世界书 | `updateWorldBookDisplay` | `templates/game.html:1436` |
| 游戏：解析系统变化 | `showSystemChanges` | `templates/game.html:1498` |
| 游戏：变化通知队列 | `showNotifications` | `templates/game.html:1561` |
| 游戏：切换系统面板 | `togglePanel` | `templates/game.html:1594` |
| 游戏：关闭更多菜单 | `closeMoreMenu` | `templates/game.html:1604` |
| 游戏：刷新系统面板 | `updatePanelDisplay` | `templates/game.html:1609` |
| 游戏：渲染人物关系 | `renderRelationships` | `templates/game.html:1619` |
| 游戏：渲染物品栏 | `renderInventory` | `templates/game.html:1655` |
| 游戏：渲染状态效果 | `renderConditions` | `templates/game.html:1687` |
| 游戏：渲染事件日志 | `renderJournal` | `templates/game.html:1714` |
| 游戏：导出菜单 | `toggleExportMenu` | `templates/game.html:1743` |
| 游戏：读取本地存档 | `_loadAllSaves` | `templates/game.html:1755` |
| 游戏：写入本地存档 | `_writeAllSaves` | `templates/game.html:1759` |
| 游戏：请求并保存槽位 | `_fetchAndSaveSlot` | `templates/game.html:1773` |
| 游戏：快速存档 | `quickSave` | `templates/game.html:1802` |
| 游戏：手动存档 | `manualSave` | `templates/game.html:1810` |
| 游戏：自动存档 | `autoSave` | `templates/game.html:1836` |
| 游戏：读取槽位 | `loadSave` | `templates/game.html:1842` |
| 游戏：导入存档文件 | `importSaveFile` | `templates/game.html:1865` |
| 游戏：删除槽位 | `deleteSave` | `templates/game.html:1894` |
| 游戏：导出单槽位 | `exportSave` | `templates/game.html:1905` |
| 游戏：渲染存档列表 | `renderSaveSlots` | `templates/game.html:1919` |
| 游戏：打开/关闭存档管理 | `openSaveManager` / `closeSaveManager` | `templates/game.html:1969` / `:1973` |
| 游戏：导出存档文件 | `saveGame` | `templates/game.html:1978` |
| 游戏：导出 TXT | `exportText` | `templates/game.html:1993` |
| 游戏：导出 JSON | `exportJSON` | `templates/game.html:2011` |
| 游戏：更多菜单 | `toggleMoreMenu` | `templates/game.html:2037` |
| 游戏：键盘快捷键 | DOM keydown | `templates/game.html:2054` |
| 结局：构造结局数据 | `ENDING_DATA` | `templates/ending.html:357` |
| 结局：渲染与评分动画 | `render` / `animateScore` | `templates/ending.html:390` / `:433` |
| 结局：构建导出 HTML | `buildExportHTML` | `templates/ending.html:698` |
| 结局：生成人生漫画 | `generateImage` | `templates/ending.html:813` |
| 结局：导出 HTML | `exportHTML` | `templates/ending.html:879` |
| 结局：导出 PNG | `exportImage` | `templates/ending.html:891` |
| 记录：加载公开记录 | `loadRecords` | `templates/records.html:81` |
| 记录：筛选/排序 | `applyFilter` | `templates/records.html:91` |
| 记录：分页渲染 | `renderPage` | `templates/records.html:109` |
| 记录：时间线构建 | `buildTimelineHTML` | `templates/records.html:155` |
| 记录：详情展示 | `showDetail` | `templates/records.html:258` |
| 记录：返回列表 | `backToList` | `templates/records.html:308` |
| 记录：导出 HTML | `exportRecHTML` | `templates/records.html:316` |
| 记录：导出 PNG | `exportRecImage` | `templates/records.html:350` |
| 全局：读取设置 | `loadSettings` | `templates/base.html:1301` |
| 全局：保存设置 | `saveSettings` | `templates/base.html:1312` |
| 全局：深色模式 | `toggleDarkMode` | `templates/base.html:1323` |
| 全局：背景音乐 | `toggleMusic` | `templates/base.html:1335` |
| 全局：初始化背景音乐 | `initBGM` | `templates/base.html:1357` |
| 全局：设置弹窗 | `toggleSettings` / `closeSettings` | `templates/base.html:1390` / `:1396` |
| 全局：Toast | `showToast` | `templates/base.html:1402` |
| 全局：启用自定义 LLM | `toggleOverride` | `templates/base.html:1411` |
| 全局：应用设置并发送 API | `applyAndClose` | `templates/base.html:1421` |

### 10.2 `base.html` 的 LLM 设置流程

`base.html:1297` 开始的前端脚本管理设置：

1. 输入保存到 `sessionStorage`，不落服务器。
2. `applyAndClose()` 读取这些值，构造 JSON。
3. `fetch('/api/llm-config', { method: 'POST', body: JSON.stringify(body) })`。
4. 后端把配置写入 `session['llm_override']`。
5. 后续 LLM 请求时，后端通过 override 优先使用这些参数。

前端 `sessionStorage` key 与后端字段的对应关系见 `base.html:1421`。

### 10.3 `game.html` 核心交互

游戏页有两个 script 块：

- `game.html:874`：将同一年份的历史事件合并渲染。
- `game.html:1038`：主逻辑。

核心变量：

- `eventHistory`：由服务端 `game.history | tojson` 注入。
- `currentChoices`：由 `game.pending_choices` 注入。
- `currentWorldTags`：由 `world_tags` 注入。
- `gameRelationships / gameInventory / gameConditions / gameJournal`：新系统状态。

核心流程：

1. `continueLife()` → `POST /game/<world_id>/next`。
2. 收到响应后更新：
   - `pendingEvents`
   - `pendingChoices`
   - 世界标签
   - 人物关系
   - 物品栏
   - 状态效果
   - 事件日志
   - 运势颜色
3. `showNextEvent()` 逐个展示事件。
4. 展示完后 `showChoices()` 显示 3 个 AI 选项和自定义输入。
5. `submitChoice()` → `POST /game/<world_id>/choose`。
6. 再点击“继续人生”，循环。

### 10.4 前端多槽位存档

代码位于 `game.html:1749`：

- localStorage key：`ai_life_saves_v1`
- 最多 5 个手动槽位 + 1 个 `auto` 自动槽位
- 每次成功推进后调用 `autoSave()`
- `_fetchAndSaveSlot` 调用 `GET /game/save` 获取完整存档 JSON
- `loadSave` 调用 `POST /game/load-json` 恢复
- 也支持从文件导入、导出单槽位 JSON

### 10.5 结局页和生图轮询

`ending.html:813`：

- `generateImage()` 先 `POST /api/generate-image` 拿 `task_id`。
- 之后每 10 秒 `GET /api/generate-image/status/<task_id>`。
- 成功后把 `result.url` 放进 `<img>`。

导出：

- HTML 导出：`buildExportHTML()` 和 `exportHTML()`。
- PNG 导出：按需加载 `html2canvas`，把 `#ending-page` 转成 canvas 下载。

### 10.6 记录页

`records.html:74`：

- `loadRecords()` → `GET /api/records`
- 支持按日期/分数排序、按世界名/玩家名搜索
- `showDetail(filename)` → `GET /api/records/<filename>`
- 详情支持 HTML/PNG 导出

## 11. 前后端通信方式总结

该项目没有 REST 风格的统一封装，前端直接使用原生 `fetch`：

- 页面表单和流程提交：`POST` 到当前 `location.href`，响应 JSON 中的 `next_step` 作为跳转目标。
- LLM 设置：`POST /api/llm-config`，JSON。
- 核心游戏推进：`POST /game/<world_id>/next`，JSON。
- 玩家选择：`POST /game/<world_id>/choose`，JSON。
- 存档导出/恢复：`GET /game/save`、`POST /game/load`、`POST /game/load-json`。
- 记录读取：`GET /api/records`、`GET /api/records/<path:filename>`。
- 生图：异步 task + 轮询。

页面之间的跳转优先采用服务端返回的 `next_step`，不硬编码完整后续 URL。

## 12. 数据持久化位置

| 数据 | 路径/位置 | 生命周期 |
|---|---|---|
| 当前游戏状态 | Flask-Session 文件 | 3 小时，或浏览器 session 结束 |
| 公开/隐藏记录 | `records/*.json` | 永久 |
| 生图图片 | `static/generated/*.jpg` | 永久 |
| 前端设置 | `sessionStorage` | 关闭标签页销毁 |
| 前端手动/自动存档 | `localStorage` | 浏览器长期保存 |
| 服务端配置 | `config.json` + 环境变量 | 持久，热重载 |

## 13. 安全与注意事项

- `SECRET_KEY` 默认从环境变量或 `config.json -> app.secret_key` 读取；都不存在时随机生成，重启会导致 session 失效。
- `records/`、`.sessions/`、`config.json` 默认被 `.gitignore` 忽略，不应提交 API Key。
- 公开记录接口会跳过文件名含 `nodisplay` 的 JSON。
- `api_record_detail` 有 `resolve()` + `is_relative_to()` 路径穿越防护。
- 游戏记录保存前会调用 `moderate_content_text` 做 LLM 内容审核；审核失败则不保存。
- 生图任务在进程内 `ThreadPoolExecutor` 中执行，重启进程会丢失未完成任务。
- 前端设置面板提示 API Key 只存在浏览器 `sessionStorage`，但实际会通过 `/api/llm-config` 传到后端 session，关闭标签后不会保留。

## 14. 常见修改入口

### 14.1 新增预设世界

1. 修改 `game_data.py:109` 的 `WORLDS`，增加世界对象。
2. 如有初始世界标签，在 `game_data.py:177` 的 `WORLD_TAG_DEFAULTS` 增加。
3. 如需专属配色，在 `templates/base.html` 的 `[data-theme="world_id"]` 区域添加 CSS。
4. 确认 `prompt` 和 `traits` 满足前端属性分配要求。

### 14.2 新增页面

1. 在 `routes/pages.py` 添加 `@pages_bp.route`。
2. 在 `templates/` 新建模板，继承 `base.html`。
3. 如需要入口，可修改 `index.html` 或相关模板。

### 14.3 新增 API

1. 在 `routes/api.py` 添加 `@api_bp.route`。
2. 保持和现有 API 一致：返回 JSON，使用 `jsonify`；页面跳转使用 `next_step`。
3. 如需要访问 LLM，使用 `_get_llm_client()`；访问配置使用 `_get_llm_config()`。

### 14.4 调整 LLM Prompt

主要位置：

- 人生事件：`llm_client.py:171`
- 身世生成：`llm_client.py:513`
- 结局评价：`llm_client.py:596`
- 漫画提示词：`llm_client.py:792`

### 14.5 调整游戏数据合并逻辑

- 属性变化：`routes/api.py:130`
- 世界标签变化：`world_tags.py:23`
- 人物关系/物品/状态/日志：`routes/api.py` 的 `game_next`
- 存档记录结构：`game_utils.py:157`

## 15. 阅读顺序建议

如果第一次进入这个项目，建议按以下顺序读：

1. `app.py`
2. `routes/__init__.py`
3. `routes/pages.py`
4. `routes/api.py`
5. `game_data.py`
6. `game_utils.py`
7. `world_tags.py`
8. `llm_client.py`
9. `templates/base.html`
10. `templates/game.html`
11. `templates/ending.html`
12. 其他页面模板按需阅读

这个顺序从“应用如何启动”到“数据如何被保存”，再到“LLM 如何参与叙事”和“前端如何消费服务端数据”，可以完整串起项目。
