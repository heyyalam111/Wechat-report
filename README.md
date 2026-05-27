# Wechat-report

语言：中文 | [English](README_EN.md)

`Wechat-report` 是一个微信群聊记录分析工具。它批量读取微信群聊消息，按时间窗口自动识别话题，计算话题价值分数，并为每个群聊生成现代化 HTML 报告。

## 功能特性

- 批量处理多个微信群聊。
- 支持 `今天`、`昨天` 和 `YYYY-MM-DD` 日期写法，也支持逗号分隔多个日期。
- 优先使用 `chatlog` HTTP API，失败时可回退到本地解密数据库。
- 按 30 分钟窗口聚合消息，自动提取得分最高的 3 个话题。
- 基于消息数、字符数、参与人数和关键词计算话题价值分。
- 输出每个群聊一个 HTML 报告。

## 仓库结构

```text
.
├── chatlog_analyzer.py      # 主程序
├── run.py                   # 快速启动脚本
├── skill.md                 # Claude Code Skill 描述
├── prompt.md                # 执行提示词
├── 群聊清单.example.md      # 配置示例
└── README.md
```

## 环境要求

- Python 3.9+
- Python 包：`requests`
- 可选：`chatlog.exe`，用于读取微信聊天记录 HTTP API
- 可选：解密后的微信数据库，例如 `MSG0_decrypted.db/de_MSG0.db`

安装依赖：

```bash
pip install requests
```

## 快速开始

1. 复制配置示例：

```bash
cp 群聊清单.example.md 群聊清单.md
```

Windows PowerShell:

```powershell
Copy-Item 群聊清单.example.md 群聊清单.md
```

2. 编辑 `群聊清单.md`：

```markdown
# 群聊清单

## 【正式班】AI编程社团
- 日期: 今天
- 格式: HTML
```

3. 运行：

```bash
python run.py
```

报告会生成在：

```text
chatlog_reports_YYYYMMDD/
```

## 数据源配置

### 使用 chatlog API

设置环境变量：

```powershell
$env:CHATLOG_PATH="chatlog.exe"
$env:WECHAT_DATA_DIR="你的微信数据目录"
$env:CHATLOG_WORK_DIR="chatlog 工作目录"
python run.py
```

脚本会尝试获取 WeChat 进程、解密数据库并启动 `http://127.0.0.1:5030` 的 chatlog 服务。

### 使用本地数据库

```bash
python chatlog_analyzer.py --db "MSG0_decrypted.db/de_MSG0.db" --config "群聊清单.md"
```

如果有 `chatrooms.csv`，脚本会用它将群名映射到群 ID。

## 命令参数

```bash
python chatlog_analyzer.py --config 群聊清单.md --db MSG0_decrypted.db/de_MSG0.db --output reports --auto-date
```

| 参数 | 说明 |
|---|---|
| `--config` | 群聊清单文件，默认 `群聊清单.md` |
| `--db` | 本地解密数据库路径 |
| `--output` | 输出目录 |
| `--auto-date` | 使用可用数据的最新日期 |

## 日期写法

| 写法 | 说明 |
|---|---|
| `今天` | 当前日期 |
| `昨天` | 前一天 |
| `2026-02-09` | 指定日期 |
| `今天,昨天` | 多日期，会拆成多个任务 |

## Claude Code Skill

`skill.md` 定义了 Claude Code 触发说明。把本仓库放在 Claude Code 可访问位置后，可用类似请求触发：

```text
分析微信群聊记录并生成报告
```

## 常见问题

| 问题 | 处理 |
|---|---|
| 找不到群 ID | 检查群名是否准确，或提供 `chatrooms.csv` |
| `chatlog` 不可用 | 检查 `WECHAT_DATA_DIR`、`CHATLOG_WORK_DIR` 和微信登录状态 |
| 无消息 | 确认日期与数据源中实际消息日期一致，或加 `--auto-date` |
| 数据库不存在 | 使用 `--db` 指定解密后的数据库路径 |

## 许可证

MIT
