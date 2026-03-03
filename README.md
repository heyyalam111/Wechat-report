# Wechat-report

微信群聊记录分析工具 - 批量分析微信群聊记录并生成精美HTML报告。

## 功能特性

- 📅 **自动日期识别** - 只需写"今天"，脚本自动转换为当前日期
- 📊 **智能话题分析** - 按30分钟自动分组消息
- 🎯 **价值评分** - 基于消息数、参与者、关键词计算话题价值
- 🔥 **自动选择最有价值的3个话题**
- 🎨 **现代化深色主题HTML报告**
- 📦 **支持批量处理多个群聊**

## 快速开始

### 1. 创建群聊清单

在当前目录创建 `群聊清单.md`：

```markdown
# 群聊清单

## 【正式班】AI编程社团
- 日期: 今天
- 格式: HTML
```

### 2. 运行分析

```bash
python run.py
```

报告将生成在 `chatlog_reports_YYYYMMDD/` 目录。

## 环境配置

### 使用 chatlog API (推荐)

需要先安装 [chatlog](https://github.com/Grt1228/chatlog) 并配置：
- 设置环境变量 `WECHAT_DATA_DIR`: 微信数据目录
- 设置环境变量 `CHATLOG_WORK_DIR`: chatlog 工作目录
- 或修改 `chatlog_analyzer.py` 中的路径配置

### 使用本地数据库

1. 解密微信数据库 (参考 [WechatMsg](https://github.com/MeetPython/WechatMsg))
2. 指定数据库路径: `python chatlog_analyzer.py --db "你的数据库路径"`

## 项目结构

```
Wechat-report/
├── chatlog_analyzer.py    # 主程序
├── run.py                 # 快速启动脚本
├── skill.md              # Claude Code Skill 描述
├── prompt.md             # 执行提示词
├── 群聊清单.example.md   # 配置示例
└── README.md             # 本文件
```

## 日期格式

| 写法 | 说明 |
|------|------|
| `今天` | 当天 |
| `昨天` | 前一天 |
| `2026-02-09` | 指定日期 |

## 许可证

MIT
