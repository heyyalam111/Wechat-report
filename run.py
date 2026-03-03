#!/usr/bin/env python3
"""
Chatlog Analyzer - 快速启动脚本
自动检测环境并执行分析
"""

import sys
import os
from pathlib import Path

# 查找数据库
db_paths = [
    "MSG0_decrypted.db/de_MSG0.db",
    "MSG0_decrypted.db\\de_MSG0.db",
    "../MSG0_decrypted.db/de_MSG0.db",
]

db_path = None
for path in db_paths:
    if Path(path).exists():
        db_path = path
        break

if db_path:
    sys.argv.extend(["--db", db_path])

# 查找配置文件
if Path("群聊清单.md").exists():
    sys.argv.extend(["--config", "群聊清单.md"])

# 添加自动日期参数
sys.argv.extend(["--auto-date"])

from chatlog_analyzer import main

if __name__ == "__main__":
    main()
