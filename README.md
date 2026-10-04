# AI 人生重开手帐

AI 驱动的互动人生模拟器。每次开局都是一个全新的故事。

**演示地址**: https://ai.baka.asia

---

## 快速开始

```bash
pip install flask flask-session requests
python app.py
```

打开浏览器访问 `http://localhost:3000`

### Docker

```bash
docker build -t ai-life .
docker run -d -p 3000:3000 \
  -e LLM_ENABLED=true \
  -e LLM_API_KEY=sk-xxxx \
  -e LLM_API_BASE=https://api.openai.com/v1 \
  -e LLM_MODEL=gpt-4o \
  ai-life
```

---

## 玩法流程

1. **选择世界** -- 战锤40K / 明日方舟 / 蔚蓝档案 / 逃离后室 / 魔法世界 / 武侠江湖 / 末日废土 / 自定义
2. **身份设定** -- 性别 + 种族（支持自定义种族描述）+ 命运背景
3. **天赋抽取** -- 随机抽取 3 个天赋（普通/稀有/史诗/传说）
4. **属性分配** -- 分配属性点，按 ↑↑↓↓←→←→ 解锁无限模式
5. **开始人生** -- 点击展开每一年/层级，属性随事件动态变化
6. **结局评分** -- 人生结束时 AI 给出评分和总结

---

## 预设世界

| 世界 | 属性 | 说明 |
|------|------|------|
| 战锤40K | 力量、意志、智慧、运气 | 巢都底层崛起，在黑暗未来中为生存而战 |
| 蔚蓝档案 | 勇气、谋略、战力、体质 | 扮演老师，拯救学生（含阿拜多斯篇、游戏开发部篇） |
| 逃离后室 | 理智、体能、感知、运气 | 阈限空间求生（含Level 0、4、5、6、7起始点，自由跨层探索） |
| 明日方舟 | 战斗、源石技艺、战术、意志 | 源石感染、天灾横行，在废墟中为生存而战 |
| 魔法世界 | 魔力、智慧、勇气、运气 | 踏入魔法世界，度过你的巫师一生 |
| 武侠江湖 | 内力、身法、悟性、侠义 | 刀光剑影的江湖世界，书写你的侠客传奇 |
| 末日废土 | 体质、感知、意志、魅力 | 核战后的荒芜大地，在辐射中求生重建 |
| 自定义 | 自由设定 | 可自由设定名称、描述、属性和世界规则 |

- **蔚蓝档案**：支持章节选择，可选择阿拜多斯篇或游戏开发部篇的独立剧情线，使用「周」作为时间单位，结局为任务型。
- **逃离后室**：类似蔚蓝档案的二级选择模式，选择的 Level 仅作为流浪者切入后室的初始起点；探索中可通过切入（No-clip）、暗门、电梯或失足跌落**自由穿越到任意别的 Level**；以 `level` 字段标识当前身处层级，理智归零将异化为悲尸。

---

## 新版本特性

### 人物关系系统

LLM 在生成事件时会同步维护人物关系网。你遇到的每个人物都有姓名、关系类型和好感度，好感度会随你的选择动态变化。

### 物品收集

关键事件中可以获得物品，物品栏记录你这一生收集到的所有道具。

### 状态追踪

角色会获得各种持续状态（如「受伤」「中毒」「声名远播」），这些状态会影响后续事件的发展方向。

### 事件日志

LLM 会自动提取关键事件写入日志，在结局回顾时可以快速浏览人生中的重要节点。

### 世界标签系统

每个世界都有一套多维标签（社会结构、自然环境、经济体系、超自然、人口构成、文化面貌），默认分布各不相同；你的选择会动态改变标签数值，进而影响后续事件的走向。

### 命运背景

身份设定阶段可以填写自定义命运背景，LLM 会将其融入整个人生叙事中。

### 自定义种族

除了预设种族，可以自由填写种族名称和描述，LLM 会据此设计相应的世界观和事件。

### AI 生图

结局页面可以一键生成人生四格漫画。LLM 先根据人生经历构建详细的分镜提示词，再调用生图模型生成图片。图片保存在本地，可在历史记录中查看。

### 内容审核

记录保存前会先经 LLM 审核，过滤违规内容后才写入文件。

### 记录可控

命运预览页可填写玩家名（限 12 字）并选择是否公开记录，公开的记录会显示在历史记录页面。

### 历史记录增强

历史记录详情页可展示生成的四格漫画图片，支持按日期和分数排序、按世界名和玩家名搜索。

### 导出功能

结局页面和历史记录详情页均支持导出为 HTML 文件或 PNG 图片（基于 html2canvas）。

### 配置热重载

修改 `config.json` 后无需重启服务，应用会自动检测文件变化并重新加载配置。

### 主题曲

项目包含原创 MIDI 主题曲和简谱，可通过 `/theme_music` 路径访问。

---

## 设置面板

点击页面右下角的 **LLM 设置** 按钮可打开设置面板。所有设置仅保存在浏览器 sessionStorage 中，关闭标签页即清除。

### 自定义 LLM（可选）

| 选项 | 说明 |
|------|------|
| 启用开关 | 开启后填写自定义 LLM 参数 |
| API 地址 | 任意 OpenAI 格式 API |
| API Key | 仅保存在浏览器中，关闭标签页即清除 |
| 模型名称 | 如 gpt-4o、deepseek-chat |
| Temperature / Top P | 采样参数 |

### 通用设置

| 选项 | 说明 |
|------|------|
| Max Tokens | LLM 输出最大 Token 数 |
| 年数范围 | 每次 LLM 生成几年（最小/最大，随机） |
| JSON 输出模式 | 启用 json_object 格式（部分模型不支持） |
| 深色模式 | 一键切换暗色主题 |

### 生图设置

| 选项 | 说明 |
|------|------|
| 生图 API 地址 | 兼容 OpenAI 格式的生图接口 |
| 生图 API Key | 生图专用 Key |
| 生图模型 | 如 dall-e-3、flux 等 |
| 图片尺寸 | 如 1024x1024 |

---

## 配置项

编辑 `config.json`：

```json
{
  "llm": {
    "enabled": true,
    "api_base": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o",
    "temperature": 0.9,
    "max_tokens": 8192,
    "batch_min": 1,
    "batch_max": 3,
    "event_words": "50-150",
    "writing_style": "",
    "custom_request_body": {},
    "json_mode": false
  },
  "image_gen": {
    "enabled": false,
    "api_base": "https://api.openai.com/v1",
    "api_key": "",
    "model": "dall-e-3",
    "size": "1024x1024",
    "quality": "standard",
    "style": "vivid"
  },
  "app": {
    "port": 3000,
    "debug": true
  }
}
```

### 环境变量

| 变量 | 说明 |
|------|------|
| `LLM_ENABLED` | 启用 LLM（true/false） |
| `LLM_API_BASE` | API 地址 |
| `LLM_API_KEY` | API Key |
| `LLM_MODEL` | 模型名称 |
| `LLM_TEMPERATURE` | 温度参数 |
| `LLM_MAX_TOKENS` | 最大 Token 数 |
| `IMAGE_GEN_ENABLED` | 启用生图 |
| `IMAGE_GEN_API_BASE` | 生图 API 地址 |
| `IMAGE_GEN_API_KEY` | 生图 API Key |
| `IMAGE_GEN_MODEL` | 生图模型 |

---

## 免费模型推荐

### 商汤日日新

[商汤日日新 SenseNova](https://platform.sensenova.cn/) 提供免费额度，可直接使用：

- **DeepSeek-V4-Flash** -- 免费的对话模型，适合驱动人生叙事生成，速度快、质量高
- **生图模型** -- 免费文生图模型，可直接用于生图功能

注册后获取 API Key，将 API 地址设为 `https://api.sensenova.cn/v1`，模型名设为 `deepseek-v4-flash` 即可。生图功能同理，填入对应的生图模型名称。

---

## 技术栈

- **后端**: Flask + Flask-Session
- **前端**: 纯 HTML/CSS/JS
- **AI**: 支持 OpenAI 格式的任意 LLM API

---

## 知识产权与致谢 (Copyright & Attribution)

本项目的「逃离后室」模式基于由 **后室 Wikidot 社区 (The Backrooms Wiki)** 共创的《后室》世界观开发，并严格遵循知识共享署名-相同方式共享 3.0 协议 (**Creative Commons Attribution-ShareAlike 3.0 License, CC BY-SA 3.0**)。

在此特别感谢并注明后室核心概念及各层级原作者的卓越创作贡献：

1. **后室（The Backrooms）原始概念与起源**：
   - 概念最初由 **4chan /x/ 板块匿名用户 (Anonymous)** 于 2019 年 5 月 12 日发布。
2. **各层级原作者与页面归属**：
   - **Level 0 (Tutorial Level / 平淡之室)**：基于 4chan 原始起源贴，由 **The Backrooms Community (Wikidot 社区)** 共创维护。
   - **Level 4 (Abandoned Office / 废弃办公室)**：作者为 **Skeptical_Spaghetti** (Wikidot)。
   - **Level 5 (Terror Hotel / 恐怖旅馆)**：作者为 **D-S** 及社区贡献者 (Wikidot)。
   - **Level 6 (Lights Out / 熄灯)**：作者为 **BlueSign** 与 **Skeptical_Spaghetti** (Wikidot)。
   - **Level 7 (Thalassophobia / 深海)**：作者为 **LordT3h** 与 **Skeptical_Spaghetti** (Wikidot)。
3. **核心设定概念**：
   - 切入/卡出 (No-clip)、杏仁水 (Almond Water)、实体 (Entities: 微笑体、窃皮者、死亡飞蛾、悲尸等) 及 M.E.G. (主要探索者组织) 设定均来源于后室社区创作者共同贡献，遵循 CC BY-SA 3.0 许可。
   - 更多详情可参阅官方网站：[The Backrooms Wikidot](http://backrooms-wiki.wikidot.com/) 与 [后室中文维基](https://backrooms-wiki.wikidot.com/zh-cn/)。

