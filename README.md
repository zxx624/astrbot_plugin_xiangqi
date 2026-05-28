# astrbot_plugin_xiangqi

一个基于 **AstrBot v4.24.x** 的中国象棋插件，使用坐标制走棋。

当前 **2.0.0** 版本定位：

- 本地规则校验和会话管理
- xqwlight 引擎负责 Bot 走棋决策
- LLM 只负责 Bot 走棋后说一句人格台词，不参与下棋决策
- 棋盘图片渲染
- 支持在 AstrBot WebUI 修改 AI 后端、xqwlight 参数、台词人格提示词

仓库地址：`https://github.com/zxx624/astrbot_plugin_xiangqi`

---

## 功能

- `象棋新局`：开始新对局，默认用户执红，Bot 执黑
- `象棋执黑`：开始新对局，用户执黑，Bot 先手走红方一步
- `走棋 <from> <to>`：按坐标走棋，例如 `走棋 b9 c7`
- `棋盘`：查看当前棋盘图片
- `悔棋`：撤销上一整个回合（用户一步 + Bot 一步）
- `认输`：结束当前对局
- `提示`：让插件给出一个可行着法建议
- `象棋状态`：查看当前执棋方、轮到谁、AI 后端和搜索深度

Bot 走棋后，如果启用了 LLM 台词，会额外发送一条独立消息气泡，例如：

```text
「这步先压住你，别急着送。」
```

---

## 2.0.0 新增

### xqwlight 引擎后端

默认使用内置 `engine/bin/xqwlight-cli.jar` 作为 Bot 走棋引擎。

插件仍然负责：

- 棋局状态
- 合法走法校验
- 坐标解析
- 图片渲染
- 会话存档

xqwlight 只负责从当前局面中选择一步棋。如果 xqwlight 超时、Java 不可用、返回非法走法，插件会自动回退到 Python 内置搜索，保证对局不中断。

### LLM 人格台词

LLM 不参与选棋，只在 Bot 已经走完棋后，根据当前局势生成一句短台词。

特点：

- 使用 AstrBot 当前默认 Provider，或在 WebUI 指定 Provider
- 支持 WebUI 修改人格提示词
- 台词超时/失败时静默跳过，不影响棋局
- 台词作为独立消息发送，避免和“你走了 / Bot走了”混在一起太机械

---

## 坐标说明

棋盘为 **9 列 × 10 行**：

- 列：`a` 到 `i`
- 行：`0` 到 `9`
- `a0` 位于图片左上角
- 图片底部显示 `a b c d e f g h i`
- 图片左侧显示 `0 1 2 3 4 5 6 7 8 9`

方向约定：

- 红方初始在下方
- 黑方初始在上方
- 红方默认向上走（行号减小）
- 黑方默认向下走（行号增大）

---

## 命令示例

```text
象棋新局
走棋 b9 c7
棋盘
提示
悔棋
认输
```

执黑开局：

```text
象棋执黑
```

---

## 规则覆盖

已实现：

- 车直走，检查路径阻挡
- 马走日，检查蹩马腿
- 相 / 象走田，不可过河，检查塞象眼
- 士九宫内斜走一步
- 将 / 帅九宫内走一步，禁止将帅对脸
- 炮走直线，吃子时必须隔一子
- 兵 / 卒过河前仅前进，过河后可左右，不能后退
- 不能走出让己方将帅被将军的局面
- 检测将军、将死、无合法走法等结束条件

暂未覆盖：

- 长将、长捉等完整专业判和规则
- 更复杂的残局库 / 开局库

---

## 配置项

### `ai_backend`

- 类型：`string`
- 默认值：`xqwlight`
- 可选：`xqwlight` / `builtin`
- 含义：Bot 走棋后端

### `ai_depth`

- 类型：`int`
- 默认值：`2`
- 含义：Python 内置搜索层数，仅 `builtin` 后端使用

### `xqwlight_jar_path`

- 类型：`string`
- 默认值：空
- 含义：xqwlight jar 路径。留空使用插件内置 `engine/bin/xqwlight-cli.jar`

### `xqwlight_depth`

- 类型：`int`
- 默认值：`8`
- 含义：xqwlight 搜索深度，建议 6-10

### `xqwlight_timeout_ms`

- 类型：`int`
- 默认值：`1500`
- 含义：xqwlight 单步超时毫秒，超时自动 fallback

### `llm_talk_enabled`

- 类型：`bool`
- 默认值：`true`
- 含义：是否启用 Bot 走棋后人格台词

### `llm_persona_prompt`

- 类型：`text`
- 含义：人格提示词，可在 WebUI 修改

示例：

```text
你是一个正在下中国象棋的机器人棋手，嘴硬但不低俗，像有点欠揍的棋摊老手。你只在自己走棋后说一句短台词，可以调侃，可以分析，但不要长篇大论。
```

### `llm_provider_id`

- 类型：`string`
- 默认值：空
- WebUI 下拉选择 Provider
- 留空使用当前会话 / 全局默认 Provider

### `llm_model`

- 类型：`string`
- 默认值：空
- 通常不用填，留空即可

### `llm_talk_timeout`

- 类型：`int`
- 默认值：`5`
- 含义：台词生成超时秒数

### `llm_talk_max_chars`

- 类型：`int`
- 默认值：`50`
- 含义：台词最大字数，防止刷屏

### `image_scale`

- 类型：`int`
- 默认值：`1`
- 含义：棋盘图片缩放倍数

---

## 安装方法

把整个目录放进 AstrBot 插件目录，例如：

```text
/opt/astrbot1/data/plugins/astrbot_plugin_xiangqi/
```

安装依赖：

```bash
pip install -r requirements.txt
```

需要 Java 运行 xqwlight：

```bash
sudo apt install default-jre-headless
```

如果没有 Java 或 xqwlight 不可用，插件会自动回退到内置 `builtin` 后端。

部署后重启 AstrBot：

```bash
sudo systemctl restart astrbot1
```

---

## 数据存储

插件通过 `StarTools.get_data_dir()` 获取运行数据目录，并在其中保存：

- `sessions.json`：当前会话中的棋局数据
- `boards/`：渲染出的棋盘 PNG 图片

不同群 / 私聊会话分别维护自己的棋局。

---

## 代码结构

```text
astrbot_plugin_xiangqi/
├── __init__.py
├── _conf_schema.json
├── main.py
├── metadata.yaml
├── README.md
├── requirements.txt
├── engine/
│   ├── ai.py
│   ├── board.py
│   ├── parser.py
│   ├── rules.py
│   ├── xqwlight_adapter.py
│   ├── bin/xqwlight-cli.jar
│   └── xqwlight_src/
├── render/
└── storage/
```

- `main.py`：AstrBot 插件入口、命令、会话管理、LLM 台词调用
- `engine/board.py`：棋盘状态与历史记录
- `engine/rules.py`：象棋规则校验
- `engine/ai.py`：AI 后端选择与 builtin 搜索
- `engine/xqwlight_adapter.py`：FEN 转换、Java 引擎调用、走法转换
- `render/board_image.py`：棋盘 PNG 渲染
- `storage/session_store.py`：会话棋局存档

---

## 已知限制

- 不是比赛级象棋引擎
- 没有完整长将长捉判和规则
- LLM 台词质量取决于 AstrBot 当前 Provider
- xqwlight 依赖 Java；不可用时会自动 fallback，但棋力会下降

---

## 许可证

当前仓库未附带单独 LICENSE。

如果准备长期公开维护，建议补一个明确的开源许可证，例如 MIT。
