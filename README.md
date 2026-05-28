# astrbot_plugin_xiangqi

AstrBot 中国象棋对战插件。用户用坐标走棋，Bot 使用本地规则引擎 + xqwlight 走棋，LLM 只负责走棋后的短台词，不参与决策。

当前版本：**2.1.0**

## 主要特性

- 坐标制走棋：`走棋 b9 c7`
- 棋盘图片渲染
- 支持用户执红 / 执黑
- 悔棋、认输、提示、查看棋盘
- 本地规则校验：车、马、相/象、士、将/帅、炮、兵/卒
- 终局检测：将军、将死、无合法走法
- AI 后端：
  - `xqwlight`：内置 Java 引擎，默认启用
  - `builtin`：Python negamax + alpha-beta 回退
- LLM 人格台词：
  - Bot 实际走棋后才说话
  - LLM 不参与选棋，只生成气氛台词
  - 台词失败/超时会静默跳过，不影响棋局
  - 支持 WebUI 自定义人格提示词、模型、超时、字数、句数
  - 2.1.0 起每次随机 1~3 句，每句作为独立消息发送

## 2.1.0 更新

- 人格提示词更自然：默认改成“发作在群里下棋”的口吻，减少机器人解说感。
- 台词句数随机：每次走棋后随机输出 1 到 `llm_talk_max_sentences` 句，默认最多 3 句。
- 真正分段：多句台词会逐句 `yield event.plain_result(...)`，在 QQ/OneBot 下表现为独立气泡，而不是一条消息里换行。
- 输出清理增强：自动去掉编号、项目符号、`台词：` / `发作：` 前缀、引号等。

## 命令

```text
象棋新局
象棋执黑
走棋 <from> <to>
棋盘
提示
悔棋
认输
象棋状态
```

示例：

```text
象棋新局
走棋 b9 c7
棋盘
```

## 坐标说明

棋盘为 9 列 × 10 行：

- 列：`a` 到 `i`
- 行：`0` 到 `9`
- `a0` 位于棋盘图片左上角
- `i9` 位于棋盘图片右下角
- 红方初始在下方，黑方初始在上方

## 配置项

| 配置项 | 默认值 | 说明 |
|---|---:|---|
| `ai_backend` | `xqwlight` | Bot 走棋后端，`xqwlight` 或 `builtin` |
| `ai_depth` | `2` | builtin 搜索层数 |
| `xqwlight_jar_path` | 空 | 自定义 xqwlight jar 路径，留空使用内置 jar |
| `xqwlight_depth` | `8` | xqwlight 搜索深度 |
| `xqwlight_timeout_ms` | `1500` | xqwlight 单步超时毫秒 |
| `llm_talk_enabled` | `true` | 是否启用走棋后人格台词 |
| `llm_persona_prompt` | 发作人格 | WebUI 可改的人格提示词 |
| `llm_provider_id` | 空 | 台词模型 Provider，留空使用当前默认 Provider |
| `llm_model` | 空 | 台词模型名，留空使用 Provider 默认模型 |
| `llm_talk_timeout` | `5` | 台词生成超时秒数 |
| `llm_talk_max_sentences` | `3` | 每次最多台词句数，实际会随机 1 到该值 |
| `llm_talk_max_chars` | `50` | 每句台词最大字数 |
| `image_scale` | `1` | 棋盘图片缩放 |

## 架构说明

主流程：

1. 用户发送 `走棋 from to`
2. 插件用本地规则校验用户走法
3. Bot 使用 `xqwlight` 计算走法，失败则回退 builtin AI
4. 插件应用 Bot 走法并保存棋局状态
5. LLM 只根据棋局和 Bot 走法生成短台词
6. 分别发送：走棋信息、1~3条独立台词、棋盘图片

LLM 不会决定走哪一步，也不会改变棋局状态。

## 安装

复制到 AstrBot 插件目录：

```text
/opt/astrbot2/data/plugins/astrbot_plugin_xiangqi/
```

安装依赖：

```bash
pip install -r requirements.txt
```

重启 AstrBot：

```bash
sudo systemctl restart astrbot2
```

## 文件结构

```text
astrbot_plugin_xiangqi/
├── __init__.py
├── main.py
├── metadata.yaml
├── _conf_schema.json
├── README.md
├── requirements.txt
├── engine/
│   ├── ai.py
│   ├── board.py
│   ├── parser.py
│   ├── rules.py
│   ├── xqwlight_adapter.py
│   └── bin/xqwlight-cli.jar
├── render/
└── storage/
```

## 注意

- 插件保存会话状态，不同群/私聊各自维护棋局。
- xqwlight 需要服务器可运行 `java`。
- LLM 台词是锦上添花功能，超时或失败不会影响下棋。
