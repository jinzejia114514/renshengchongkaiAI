# 📖 AI 人生重开手帐

AI 驱动的互动人生模拟器。每次开局都是一个全新的故事。

## 快速开始

```bash
pip install flask flask-session requests
python app.py
```

打开浏览器访问 `http://localhost:3000`

## 玩法流程

1. **选择世界** — 现代都市 / 九州仙域 / 冷战风云 / 自定义
2. **身份设定** — 性别 + 种族（支持自定义种族）
3. **天赋抽取** — 随机抽取 3 个天赋（普通/稀有/史诗/传说）
4. **属性分配** — 分配属性点（容貌、智力、体质、家境等）
5. **开始人生** — 点击展开每一年，选择影响命运走向
6. **结局评分** — 人生结束时 AI 给出评分和总结（含环形评分图）

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
