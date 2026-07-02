# 📖 AI 人生重开手帐

AI 驱动的互动人生模拟器。每次开局都是一个全新的故事。

**演示地址** : https://ai.baka.asia

## 快速开始

```bash
pip install flask flask-session requests
python app.py
```

打开浏览器访问 `http://localhost:3000`

## 玩法流程

1. **选择世界** — 战锤40K / 明日方舟 / 蔚蓝档案 / 魔法世界 / 自定义
2. **身份设定** — 性别 + 种族（支持自定义种族）
3. **天赋抽取** — 随机抽取 3 个天赋（普通/稀有/史诗/传说）
4. **属性分配** — 分配属性点，按 ↑↑↓↓←→←→ 解锁无限模式
5. **开始人生** — 点击展开每一年，属性随事件动态变化
6. **结局评分** — 人生结束时 AI 给出评分和总结（含环形评分图）

## 预设世界

| 世界 | 属性 |
|------|------|
| 🗡 战锤40K | 力量、意志、智慧、运气 |
| 🧬 明日方舟 | 战斗、源石技艺、战术、意志 |
| 📚 蔚蓝档案 | 勇气、谋略、战力、体质 |
| ⚡ 魔法世界 | 魔力、智慧、勇气、运气 |
| ⚔️ 武侠江湖 | 内力、身法、悟性、侠义 |
| ☢️ 末日废土 | 体质、感知、意志、魅力 |
| 🌐 自定义 | 自由设定名称、描述和属性 |

## 设置面板

页面右下角 **LLM 设置** 按钮打开设置面板。所有设置仅存浏览器 sessionStorage，关标签即清除。

### 自定义 LLM（可选）
| 选项 | 说明 |
|------|------|
| 启用开关 | 开启后填写自定义 LLM 参数 |
| API 地址 | 任意 OpenAI 格式 API（DeepSeek、火山引擎等） |
| API Key | 仅存浏览器，关标签销毁 |
| 模型名称 | 如 gpt-4o、deepseek-chat |
| Temperature / Top P | 采样参数 |

### 通用设置（不依赖自定义 LLM）
| 选项 | 说明 |
|------|------|
| Max Tokens | LLM 输出最大 Token 数 |
| 年数范围 | 每次 LLM 生成几年（最小/最大，随机） |
| JSON 输出模式 | 启用 json_object 格式（部分模型不支持） |
| 深色模式 | 一键切换暗色主题 |

## 📜 历史记录

首页点击「📜 历史记录」查看其他玩家的公开人生。每页展示 5 条，支持分页。

命运预览页可填写玩家名（限 12 字）和选择是否公开记录。公开记录会在首页展示，不公开的不对外显示。

## 配置项

编辑 `config.json`：

```json
{
  "llm": {
    "enabled": true,
    "api_base": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-3.5-turbo",
    "temperature": 0.9,
    "max_tokens": 512,
    "custom_request_body": {}
  },
  "app": {
    "port": 3000,
    "debug": true
  }
}
```

## 部署

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

### 环境变量

| 变量 | 说明 |
|------|------|
| `LLM_ENABLED` | 启用 LLM（true/false） |
| `LLM_API_BASE` | API 地址 |
| `LLM_API_KEY` | API Key |
| `LLM_MODEL` | 模型名称 |
| `LLM_TEMPERATURE` | 温度参数 |
| `LLM_MAX_TOKENS` | 最大 Token 数 |

## 技术栈

- **后端**: Flask + Flask-Session
- **前端**: 纯 HTML/CSS/JS
- **AI**: 支持 OpenAI 格式的任意 LLM API
