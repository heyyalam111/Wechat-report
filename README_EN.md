# Wechat-report

Language: [中文](README.md) | English

`Wechat-report` is a WeChat group-chat analysis tool. It reads group messages in batches, groups messages into time windows, scores valuable discussion topics, and generates modern HTML reports for each group.

## Features

- Batch process multiple WeChat groups.
- Support `今天`, `昨天`, `YYYY-MM-DD`, and comma-separated multiple dates.
- Prefer the `chatlog` HTTP API and fall back to a local decrypted database.
- Group messages by 30-minute windows and select the top 3 topics.
- Score topics by message count, text length, participant count, and keywords.
- Generate one HTML report per group.

## Repository Layout

```text
.
├── chatlog_analyzer.py      # Main program
├── run.py                   # Quick launcher
├── skill.md                 # Claude Code Skill description
├── prompt.md                # Execution prompt
├── 群聊清单.example.md      # Config example
└── README.md
```

## Requirements

- Python 3.9+
- Python package: `requests`
- Optional: `chatlog.exe` for the WeChat chatlog HTTP API
- Optional: decrypted WeChat database, for example `MSG0_decrypted.db/de_MSG0.db`

Install dependencies:

```bash
pip install requests
```

## Quick Start

1. Copy the sample config:

```bash
cp 群聊清单.example.md 群聊清单.md
```

PowerShell:

```powershell
Copy-Item 群聊清单.example.md 群聊清单.md
```

2. Edit `群聊清单.md`:

```markdown
# 群聊清单

## 【正式班】AI编程社团
- 日期: 今天
- 格式: HTML
```

3. Run:

```bash
python run.py
```

Reports are written to:

```text
chatlog_reports_YYYYMMDD/
```

## Data Sources

### Use chatlog API

Set environment variables:

```powershell
$env:CHATLOG_PATH="chatlog.exe"
$env:WECHAT_DATA_DIR="your WeChat data directory"
$env:CHATLOG_WORK_DIR="your chatlog working directory"
python run.py
```

The script tries to detect the WeChat process, decrypt the database, and start the chatlog service at `http://127.0.0.1:5030`.

### Use a local database

```bash
python chatlog_analyzer.py --db "MSG0_decrypted.db/de_MSG0.db" --config "群聊清单.md"
```

If `chatrooms.csv` exists, the script uses it to map group names to group IDs.

## CLI Options

```bash
python chatlog_analyzer.py --config 群聊清单.md --db MSG0_decrypted.db/de_MSG0.db --output reports --auto-date
```

| Option | Description |
|---|---|
| `--config` | Group config file, default `群聊清单.md` |
| `--db` | Local decrypted database path |
| `--output` | Output directory |
| `--auto-date` | Use the latest available data date |

## Date Syntax

| Value | Meaning |
|---|---|
| `今天` | Current date |
| `昨天` | Previous day |
| `2026-02-09` | Specific date |
| `今天,昨天` | Multiple tasks |

## Claude Code Skill

`skill.md` defines the Claude Code trigger description. Once the repository is available to Claude Code, use a request such as:

```text
分析微信群聊记录并生成报告
```

## Troubleshooting

| Issue | Fix |
|---|---|
| Group ID not found | Check the group name or provide `chatrooms.csv` |
| `chatlog` unavailable | Check `WECHAT_DATA_DIR`, `CHATLOG_WORK_DIR`, and WeChat login state |
| No messages | Check the selected date or use `--auto-date` |
| Database missing | Pass the decrypted database path with `--db` |

## License

MIT
