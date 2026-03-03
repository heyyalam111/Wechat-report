#!/usr/bin/env python3
"""
Chatlog Analyzer - 批量分析微信群聊记录并生成HTML报告
支持两种数据源：
1. chatlog HTTP API (优先，需要微信登录状态)
2. 解密后的本地数据库 (备用)
"""

import json
import sqlite3
import re
import sys
import io
import subprocess
import time
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional
import argparse


# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass


class ChatlogConfig:
    """群聊配置"""
    def __init__(self, name: str, date: str, format: str = "HTML"):
        self.name = name
        self.date = date
        self.format = format


class ChatlogParser:
    """解析群聊清单MD文件"""

    @staticmethod
    def parse_date(date_str: str) -> str:
        """解析日期字符串"""
        date_str = date_str.strip().lower()
        today = datetime.now()

        if date_str == "今天":
            return today.strftime("%Y-%m-%d")
        elif date_str == "昨天":
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")
        elif re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            return date_str
        else:
            return today.strftime("%Y-%m-%d")

    @staticmethod
    def parse_dates(date_str: str) -> List[str]:
        """解析日期字符串，支持逗号分隔的多个日期"""
        dates = []
        for part in date_str.split(','):
            part = part.strip()
            if part.lower() == "今天":
                dates.append(datetime.now().strftime("%Y-%m-%d"))
            elif part.lower() == "昨天":
                dates.append((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))
            elif re.match(r'\d{4}-\d{2}-\d{2}', part):
                dates.append(part)
        return dates if dates else [datetime.now().strftime("%Y-%m-%d")]

    @staticmethod
    def parse_config_file(file_path: str) -> List[ChatlogConfig]:
        """解析群聊清单.md文件"""
        configs = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 按## 分割群聊
            sections = re.split(r'\n##\s+', content)

            for section in sections[1:]:  # 跳过第一个（标题）
                lines = section.strip().split('\n')
                if not lines:
                    continue

                name = lines[0].strip()
                date = "今天"
                format_type = "HTML"

                # 解析配置项
                for line in lines[1:]:
                    if line.strip().startswith('- 日期:'):
                        date = line.split(':', 1)[1].strip()
                    elif line.strip().startswith('- 格式:'):
                        format_type = line.split(':', 1)[1].strip()

                # 支持多日期，拆分成多个配置
                dates = ChatlogParser.parse_dates(date)
                for d in dates:
                    configs.append(ChatlogConfig(name, d, format_type))

            return configs

        except FileNotFoundError:
            print(f"错误: 找不到文件 {file_path}")
            return []
        except Exception as e:
            print(f"解析配置文件时出错: {e}")
            return []


class ChatlogAutoStarter:
    """自动启动 chatlog 服务"""

    # 可通过环境变量或配置文件自定义
    CHATLOG_PATH = os.environ.get('CHATLOG_PATH', 'chatlog.exe')
    DATA_KEY = None  # 将通过配置文件或自动获取
    DATA_DIR = os.environ.get('WECHAT_DATA_DIR', '')  # 微信数据目录
    WORK_DIR = os.environ.get('CHATLOG_WORK_DIR', '')  # chatlog工作目录

    @staticmethod
    def kill_chatlog():
        """杀掉现有的chatlog进程"""
        subprocess.run('taskkill /F /IM chatlog.exe 2>nul', shell=True)
        time.sleep(1)

    @staticmethod
    def get_wechat_pid() -> Optional[int]:
        """获取微信进程PID"""
        result = subprocess.run(
            'tasklist /FI "IMAGENAME eq WeChat.exe"',
            capture_output=True, text=True, shell=True
        )
        for line in result.stdout.split('\n'):
            if 'WeChat.exe' in line:
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1])
        return None

    @staticmethod
    def get_data_key() -> Optional[str]:
        """获取数据密钥"""
        # 首先尝试从配置文件读取 (chatlog 默认配置路径)
        try:
            # 尝试常见的 chatlog 配置路径
            possible_paths = [
                os.path.expanduser('~/.chatlog/chatlog.json'),
                os.path.expanduser('C:/Users/%s/.chatlog/chatlog.json' % os.environ.get('USERNAME', 'default')),
            ]
            for config_path in possible_paths:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                        config = json.load(f)
                    if 'history' in config and len(config['history']) > 0:
                        return config['history'][0]['data_key']
        except:
            pass

        # 尝试从微信进程获取
        wechat_pid = ChatlogAutoStarter.get_wechat_pid()
        if wechat_pid:
            cmd = [ChatlogAutoStarter.CHATLOG_PATH, 'key', '-p', str(wechat_pid)]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            for line in result.stdout.split('\n'):
                if 'Data Key:' in line:
                    return line.split('Data Key:')[1].strip().strip('[]')

        return None

    @staticmethod
    def decrypt_database(data_key: str) -> bool:
        """解密数据库"""
        cmd = [
            ChatlogAutoStarter.CHATLOG_PATH, 'decrypt',
            '-d', ChatlogAutoStarter.DATA_DIR,
            '-k', data_key,
            '-w', ChatlogAutoStarter.WORK_DIR
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        # 检查是否是平台不支持的错误
        if 'unsupported platform' in result.stdout.lower() or 'unsupported platform' in result.stderr.lower():
            print("  警告: chatlog 不支持当前 WeChat 版本 (platform v3)")
            print("  请更新 chatlog 或使用手机迁移聊天记录")
            return False

        return 'decrypt success' in result.stdout or 'success' in result.stdout.lower()

    @staticmethod
    def start_server(data_key: str) -> bool:
        """启动HTTP服务器"""
        ChatlogAutoStarter.kill_chatlog()
        time.sleep(1)

        cmd = [
            ChatlogAutoStarter.CHATLOG_PATH, 'server',
            '-d', ChatlogAutoStarter.DATA_DIR,
            '-k', data_key,
            '-w', ChatlogAutoStarter.WORK_DIR,
            '-p', 'windows',
            '-v', '3'
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # 等待启动
        for i in range(20):
            time.sleep(1)
            try:
                resp = requests.get('http://127.0.0.1:5030/api/v1/session', timeout=1)
                if resp.status_code == 200:
                    return True
            except:
                pass

        return False

    @classmethod
    def ensure_server_running(cls) -> bool:
        """确保chatlog服务器运行"""
        # 检查是否已经在运行
        try:
            resp = requests.get('http://127.0.0.1:5030/api/v1/session', timeout=3)
            if resp.status_code == 200:
                # 测试API是否真的可用
                if len(resp.text) > 10:
                    return True
        except:
            pass

        # 检查是否配置了必要的路径
        if not cls.DATA_DIR or not cls.WORK_DIR:
            print("请设置环境变量 WECHAT_DATA_DIR 和 CHATLOG_WORK_DIR")
            return False

        # 需要启动
        print("正在启动 chatlog 服务...")

        # 获取密钥
        data_key = cls.get_data_key()
        if not data_key:
            print("无法获取数据密钥")
            return False

        # 解密数据库
        decrypt_ok = cls.decrypt_database(data_key)
        if not decrypt_ok:
            print("数据库解密失败 (可能是不支持的 WeChat 版本)")
            print("解决方案:")
            print("  1. 等待 chatlog 更新支持新版本")
            print("  2. 使用手机迁移聊天记录到电脑")
            print("  3. 降级 WeChat 到较旧版本")

        # 启动服务器
        if cls.start_server(data_key):
            # 验证服务可用
            try:
                resp = requests.get('http://127.0.0.1:5030/api/v1/session', timeout=5)
                if resp.status_code == 200 and len(resp.text) > 10:
                    print("chatlog 服务已就绪")
                    return True
            except:
                pass

        print("chatlog 服务不可用")
        return False


class ChatlogAPI:
    """Chatlog HTTP API 客户端"""

    BASE_URL = "http://127.0.0.1:5030"

    def __init__(self, wechat_dir: str = None):
        self.wechat_dir = wechat_dir
        self.server_process = None

    def start_server(self, data_key: str = None) -> bool:
        """启动chatlog服务器"""
        if self.is_server_running():
            return True

        return ChatlogAutoStarter.ensure_server_running()

    def is_server_running(self) -> bool:
        """检查服务器是否在运行"""
        try:
            resp = requests.get(f"{self.BASE_URL}/api/v1/session", timeout=2)
            return resp.status_code == 200
        except:
            return False

    def get_chatrooms(self) -> Dict[str, str]:
        """获取群聊列表"""
        try:
            resp = requests.get(f"{self.BASE_URL}/api/v1/chatroom", timeout=10)
            if resp.status_code == 200:
                chatrooms = {}
                for line in resp.text.strip().split('\n'):
                    if ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            # parts[0] = talker_id, parts[1] = nickname
                            chatrooms[parts[1]] = parts[0]
                return chatrooms
        except Exception as e:
            print(f"  获取群聊列表失败: {e}")
        return {}

    def get_latest_date(self) -> Optional[str]:
        """从API获取最新消息日期"""
        try:
            resp = requests.get(f"{self.BASE_URL}/api/v1/session", timeout=10)
            if resp.status_code == 200:
                dates = re.findall(r'2026-\d{2}-\d{2}', resp.text)
                if dates:
                    return max(dates)
        except Exception as e:
            print(f"  获取最新日期失败: {e}")
        return None

    def fetch_messages(self, talker: str, date: str) -> List[Dict[str, Any]]:
        """从API获取指定日期的消息"""
        try:
            # 尝试多种日期格式
            for date_format in [date, f"{date}~{date}"]:
                resp = requests.get(
                    f"{self.BASE_URL}/api/v1/chatlog",
                    params={"talker": talker, "time": date_format},
                    timeout=30
                )
                if resp.status_code == 200 and resp.text.strip():
                    messages = []
                    lines = resp.text.strip().split('\n')

                    # 解析消息 - 格式: sender_name(sender_id) time
                    #             content (next line)
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        if not line:
                            i += 1
                            continue

                        # 匹配: 发送者(发送者ID) 时间
                        match = re.match(r'^(.+?)\((\S+)\)\s+(\d{1,2}:\d{2}:\d{2})$', line)
                        if match:
                            sender_name = match.group(1)
                            sender_id = match.group(2)
                            time_str = match.group(3)

                            # 消息内容在下一行
                            content = ""
                            if i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                if next_line:
                                    content = next_line
                                    i += 1  # skip the content line

                            messages.append({
                                'CreateTime': time_str,
                                'CreateTime_readable': time_str,
                                'TalkerId': sender_id,
                                'StrTalker': talker,
                                'StrContent': content,
                                'SenderName': sender_name,
                                'IsSender': 0
                            })

                        i += 1

                    return messages
        except Exception as e:
            print(f"  获取消息失败: {e}")
        return []


class ChatlogFetcher:
    """获取聊天记录 - 数据库方式"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_latest_date(self) -> Optional[str]:
        """获取数据库中最新消息的日期"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(date(CreateTime, 'unixepoch', 'localtime')) FROM MSG")
            result = cursor.fetchone()
            conn.close()
            if result and result[0]:
                return result[0]
        except Exception as e:
            print(f"  获取最新日期失败: {e}")
        return None

    def get_group_id_by_name(self, group_name: str, chatrooms_csv: str = None) -> str:
        """根据群名查找群ID"""
        # 首先尝试从chatrooms.csv查找
        if chatrooms_csv and os.path.exists(chatrooms_csv):
            try:
                import csv
                with open(chatrooms_csv, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['NickName'] == group_name or row.get('Remark', '') == group_name:
                            return row['Name']
            except Exception as e:
                print(f"  读取chatrooms.csv失败: {e}")

        # 尝试从数据库查找
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT StrTalker FROM MSG
                WHERE StrTalker LIKE '%@chatroom'
                LIMIT 10
            """)
            for row in cursor.fetchall():
                print(f"  可用群ID: {row[0]}")
            conn.close()
        except Exception as e:
            print(f"  查询群ID时出错: {e}")
        return None

    def fetch_messages(self, group_id: str, date: str) -> List[Dict[str, Any]]:
        """获取指定日期的消息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = """
            SELECT
                localId,
                TalkerId,
                Type,
                IsSender,
                CreateTime,
                StrTalker,
                StrContent,
                DisplayContent
            FROM MSG
            WHERE StrTalker = ?
            AND date(CreateTime, 'unixepoch', 'localtime') = ?
            ORDER BY CreateTime ASC
            """

            cursor.execute(query, (group_id, date))
            rows = cursor.fetchall()
            conn.close()

            messages = []
            for row in rows:
                messages.append({
                    'localId': row[0],
                    'TalkerId': row[1],
                    'Type': row[2],
                    'IsSender': row[3],
                    'CreateTime': row[4],
                    'CreateTime_readable': datetime.fromtimestamp(row[4]).strftime('%Y-%m-%d %H:%M:%S'),
                    'StrTalker': row[5],
                    'StrContent': row[6],
                    'DisplayContent': row[7]
                })

            return messages

        except Exception as e:
            print(f"  获取消息时出错: {e}")
            return []


class TopicAnalyzer:
    """话题分析器"""

    @staticmethod
    def group_by_time(messages: List[Dict], interval_minutes: int = 30) -> List[List[Dict]]:
        """按时间间隔分组消息"""
        if not messages:
            return []

        # 按时间排序
        sorted_msgs = sorted(messages, key=lambda m: m.get('CreateTime', 0))

        groups = []
        current_group = [sorted_msgs[0]]

        for msg in sorted_msgs[1:]:
            # Handle both Unix timestamp and readable datetime string
            try:
                if isinstance(msg.get('CreateTime'), (int, float)):
                    msg_time = msg['CreateTime']
                    prev_time = current_group[-1]['CreateTime']
                else:
                    msg_time = datetime.strptime(msg['CreateTime'], '%Y-%m-%d %H:%M:%S').timestamp()
                    prev_time = datetime.strptime(current_group[-1]['CreateTime'], '%Y-%m-%d %H:%M:%S').timestamp()
                time_diff = msg_time - prev_time
            except:
                time_diff = 0

            if time_diff <= interval_minutes * 60:
                current_group.append(msg)
            else:
                groups.append(current_group)
                current_group = [msg]

        if current_group:
            groups.append(current_group)

        return groups

    @staticmethod
    def calculate_topic_score(messages: List[Dict]) -> float:
        """计算话题价值分数"""
        # 消息数量
        msg_count = len(messages)

        # 总字符数
        total_chars = sum(len(msg.get('StrContent', '')) for msg in messages)

        # 参与者数量
        participants = len(set(msg.get('TalkerId', msg.get('StrTalker', '')) for msg in messages))

        # 关键词权重
        keywords = ['AI', '编程', 'claude', 'cursor', 'api', '模型', '工具', '问题', '解决', '代码', '学习']
        keyword_count = 0
        for msg in messages:
            content = str(msg.get('StrContent', '')).lower()
            keyword_count += sum(1 for kw in keywords if kw.lower() in content)

        # 综合评分
        score = (
            msg_count * 1.0 +
            (total_chars / 100) * 0.5 +
            participants * 2.0 +
            keyword_count * 1.5
        )

        return score

    @staticmethod
    def generate_topic_title(messages: List[Dict]) -> str:
        """生成话题标题"""
        all_text = ' '.join([msg.get('StrContent', '') for msg in messages])
        keywords = re.findall(r'[\u4e00-\u9fa5]{2,}|[A-Za-z]{3,}', all_text)
        keyword_counts = Counter(keywords)
        top_keywords = [k for k, v in keyword_counts.most_common(5) if len(k) > 2]

        if top_keywords:
            return f"关于 {', '.join(top_keywords[:3])} 的讨论"
        else:
            return "群聊讨论"

    @staticmethod
    def generate_summary(messages: List[Dict], max_length: int = 150) -> str:
        """生成话题摘要"""
        sorted_msgs = sorted(messages, key=lambda m: len(str(m.get('StrContent', ''))), reverse=True)

        summary_parts = []
        total_length = 0

        for msg in sorted_msgs[:3]:
            content = str(msg.get('StrContent', '')).strip()
            if content and total_length + len(content) < max_length:
                summary_parts.append(content[:50])
                total_length += len(content)

        return ' | '.join(summary_parts) if summary_parts else "群聊讨论内容"

    @staticmethod
    def extract_keywords(messages: List[Dict], top_n: int = 5) -> List[str]:
        """提取关键词"""
        all_text = ' '.join([msg.get('StrContent', '') for msg in messages])
        keywords = re.findall(r'[\u4e00-\u9fa5]{2,}|[A-Za-z]{3,}', all_text)
        keyword_counts = Counter(keywords)
        return [k for k, v in keyword_counts.most_common(top_n) if len(k) > 2]

    @classmethod
    def analyze_topics(cls, messages: List[Dict], top_n: int = 3) -> List[Dict]:
        """分析并选择最有价值的话题"""
        # 确保消息有正确的时间戳格式
        normalized_messages = []
        for msg in messages:
            normalized = msg.copy()
            if 'CreateTime_readable' not in normalized and 'CreateTime' in normalized:
                try:
                    if isinstance(normalized['CreateTime'], (int, float)):
                        normalized['CreateTime_readable'] = datetime.fromtimestamp(
                            normalized['CreateTime']
                        ).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            normalized_messages.append(normalized)

        # 按时间分组
        groups = cls.group_by_time(normalized_messages, interval_minutes=30)

        # 计算每个话题的分数
        topics = []
        for group in groups:
            if len(group) < 3:
                continue

            score = cls.calculate_topic_score(group)
            title = cls.generate_topic_title(group)
            summary = cls.generate_summary(group)
            keywords = cls.extract_keywords(group)

            # 获取时间范围
            try:
                if isinstance(group[0].get('CreateTime'), (int, float)):
                    start_time = datetime.fromtimestamp(group[0]['CreateTime']).strftime('%H:%M')
                    end_time = datetime.fromtimestamp(group[-1]['CreateTime']).strftime('%H:%M')
                else:
                    start_time = group[0].get('CreateTime', '')[:5]
                    end_time = group[-1].get('CreateTime', '')[:5]
            except:
                start_time = "00:00"
                end_time = "23:59"

            topics.append({
                'messages': group,
                'score': score,
                'title': title,
                'summary': summary,
                'keywords': keywords,
                'start_time': start_time,
                'end_time': end_time,
                'message_count': len(group),
                'participant_count': len(set(msg.get('TalkerId', msg.get('StrTalker', '')) for msg in group))
            })

        # 按分数排序并返回前N个
        topics.sort(key=lambda t: t['score'], reverse=True)
        return topics[:top_n]


class HTMLGenerator:
    """HTML报告生成器"""

    @staticmethod
    def generate_report(group_name: str, date: str, topics: List[Dict],
                       total_messages: int, output_path: str):
        """生成HTML报告"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{group_name} · 每日精华 | {date}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --secondary: #8b5cf6;
            --accent: #ec4899;
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --bg-hover: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            --border: #334155;
            --success: #10b981;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.6;
            overflow-x: hidden;
        }}

        .bg-gradient {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            background:
                radial-gradient(circle at 20% 50%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 40% 20%, rgba(236, 72, 153, 0.1) 0%, transparent 50%);
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
        }}

        .header {{
            text-align: center;
            margin-bottom: 60px;
            padding: 60px 20px;
            position: relative;
        }}

        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 200px;
            height: 4px;
            background: linear-gradient(90deg, var(--primary), var(--secondary), var(--accent));
            border-radius: 2px;
        }}

        .header h1 {{
            font-size: clamp(32px, 5vw, 56px);
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 50%, var(--accent) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 16px;
            letter-spacing: -0.02em;
        }}

        .header .subtitle {{
            font-size: 18px;
            color: var(--text-secondary);
            font-weight: 400;
        }}

        .header .date {{
            display: inline-block;
            margin-top: 20px;
            padding: 8px 20px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            font-size: 14px;
            color: var(--text-muted);
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 60px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border-radius: 16px;
            padding: 28px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}

        .stat-card::before {{
            content: '';
            position: absolute;
            top: -50%;
            right: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: pulse 3s ease-in-out infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 0.5; }}
            50% {{ transform: scale(1.1); opacity: 0.8; }}
        }}

        .stat-number {{
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 8px;
            position: relative;
        }}

        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
            font-weight: 500;
            position: relative;
        }}

        .section-title {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .section-title::before {{
            content: '';
            width: 6px;
            height: 32px;
            background: linear-gradient(180deg, var(--primary), var(--secondary));
            border-radius: 3px;
        }}

        .topics {{
            margin-bottom: 60px;
        }}

        .topic-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 32px;
            margin-bottom: 32px;
            transition: all 0.3s ease;
        }}

        .topic-card:hover {{
            transform: translateY(-4px);
            border-color: var(--primary);
            box-shadow: 0 20px 40px rgba(99, 102, 241, 0.2);
        }}

        .topic-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}

        .topic-title {{
            font-size: 24px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
        }}

        .topic-meta {{
            display: flex;
            gap: 16px;
            font-size: 14px;
            color: var(--text-muted);
        }}

        .topic-meta span {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .topic-summary {{
            font-size: 15px;
            color: var(--text-secondary);
            line-height: 1.7;
            margin-bottom: 16px;
        }}

        .topic-keywords {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 24px;
        }}

        .keyword-tag {{
            padding: 6px 12px;
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid var(--primary);
            border-radius: 20px;
            font-size: 13px;
            color: var(--primary);
        }}

        .messages-list {{
            display: grid;
            gap: 12px;
        }}

        .message-item {{
            background: var(--bg-hover);
            border-left: 3px solid var(--primary);
            border-radius: 8px;
            padding: 16px;
            transition: all 0.2s ease;
        }}

        .message-item:hover {{
            transform: translateX(4px);
            background: #3f4b5e;
        }}

        .message-time {{
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}

        .message-content {{
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        .footer {{
            text-align: center;
            padding: 40px 20px;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 14px;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 20px 16px;
            }}

            .header {{
                padding: 40px 16px;
            }}

            .stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        ::-webkit-scrollbar {{
            width: 10px;
        }}

        ::-webkit-scrollbar-track {{
            background: var(--bg-dark);
        }}

        ::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 5px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: var(--primary);
        }}
    </style>
</head>
<body>
    <div class="bg-gradient"></div>

    <div class="container">
        <header class="header">
            <h1>{group_name}</h1>
            <p class="subtitle">每日精华 · 智能话题分析</p>
            <div class="date">{date}</div>
        </header>

        <section class="stats">
            <div class="stat-card">
                <div class="stat-number">{total_messages}</div>
                <div class="stat-label">总消息数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(topics)}</div>
                <div class="stat-label">热门话题</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{sum(t['participant_count'] for t in topics)}</div>
                <div class="stat-label">参与讨论</div>
            </div>
        </section>

        <section class="topics">
            <h2 class="section-title">热门话题</h2>
"""

        # 添加话题
        for i, topic in enumerate(topics, 1):
            html += f"""
            <div class="topic-card">
                <div class="topic-header">
                    <div>
                        <h3 class="topic-title">#{i} {topic['title']}</h3>
                        <div class="topic-meta">
                            <span>{topic['start_time']} - {topic['end_time']}</span>
                            <span>{topic['message_count']} 条消息</span>
                            <span>{topic['participant_count']} 人参与</span>
                        </div>
                    </div>
                </div>

                <p class="topic-summary">{topic['summary']}</p>

                <div class="topic-keywords">
"""
            for keyword in topic['keywords']:
                html += f'                    <span class="keyword-tag">{keyword}</span>\n'

            html += """                </div>

                <div class="messages-list">
"""

            # 添加消息（最多显示5条）
            for msg in topic['messages'][:5]:
                content = str(msg.get('StrContent', ''))
                time_display = msg.get('CreateTime_readable', msg.get('CreateTime', ''))
                if len(content) > 200:
                    content = content[:200] + '...'

                html += f"""                    <div class="message-item">
                        <div class="message-time">{time_display}</div>
                        <div class="message-content">{content}</div>
                    </div>
"""

            html += """                </div>
            </div>
"""

        html += f"""        </section>

        <footer class="footer">
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 由 Wechat-report 自动生成</p>
        </footer>
    </div>
</body>
</html>
"""

        # 保存文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='批量分析微信群聊记录')
    parser.add_argument('--config', default='群聊清单.md', help='配置文件路径')
    parser.add_argument('--db', default='MSG0_decrypted.db/de_MSG0.db', help='数据库路径')
    parser.add_argument('--auto-date', action='store_true', help='自动获取最新日期')
    parser.add_argument('--output', default=None, help='输出目录')

    args = parser.parse_args()

    # 解析配置
    print("正在读取群聊清单...")
    configs = ChatlogParser.parse_config_file(args.config)

    if not configs:
        print("错误: 未找到有效的群聊配置")
        return

    print(f"找到 {len(configs)} 个群聊配置")

    # 创建输出目录
    output_dir = args.output or f"chatlog_reports_{datetime.now().strftime('%Y%m%d')}"
    Path(output_dir).mkdir(exist_ok=True)

    # 优先尝试 chatlog API，如果失败则使用本地数据库
    use_api = False
    chatlog_api = None

    # 自动启动 chatlog 服务
    if ChatlogAutoStarter.ensure_server_running():
        chatlog_api = ChatlogAPI()
        # 测试API是否可用
        try:
            test_resp = requests.get('http://127.0.0.1:5030/api/v1/session', timeout=5)
            if test_resp.status_code == 200:
                use_api = True
                print("chatlog API 可用")
        except:
            print("chatlog API 无响应，将使用本地数据库")

    # 如果使用API，自动获取最新日期
    if use_api and chatlog_api and args.auto_date:
        latest_date = chatlog_api.get_latest_date()
        if latest_date:
            today = datetime.now().strftime('%Y-%m-%d')
            if latest_date != today:
                print(f"注意: 最新数据日期为 {latest_date}，不是今天({today})")
            print(f"使用最新日期: {latest_date}")
            for config in configs:
                if config.date.lower() in ['今天', '昨天']:
                    config.date = latest_date

    # 数据库方式获取（备用或主要）
    db_fetcher = None
    if not use_api:
        print("使用本地数据库...")
        if os.path.exists(args.db):
            db_fetcher = ChatlogFetcher(args.db)

            # 自动获取最新日期
            if args.auto_date:
                latest_date = db_fetcher.get_latest_date()
                if latest_date:
                    print(f"数据库最新日期: {latest_date}")
                    for config in configs:
                        if config.date.lower() in ['今天', '昨天']:
                            config.date = latest_date
                            print(f"  {config.name}: {latest_date}")
        else:
            print(f"本地数据库不存在: {args.db}")

    # 获取chatrooms.csv路径
    config_path = Path(args.config)
    chatrooms_csv = str(config_path.parent / "chatrooms.csv")

    # 处理每个群聊
    for config in configs:
        print(f"\n处理群聊: {config.name}")

        # 解析日期
        target_date = ChatlogParser.parse_date(config.date)
        print(f"  日期: {target_date}")

        # 获取群ID
        group_id = None

        # 首先尝试从chatrooms.csv获取（更准确）
        if os.path.exists(chatrooms_csv):
            try:
                import csv
                with open(chatrooms_csv, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['NickName'] == config.name:
                            group_id = row['Name']
                            break
            except Exception as e:
                print(f"  读取群聊列表失败: {e}")

        # 如果没找到，尝试从API获取
        if not group_id and use_api and chatlog_api:
            chatrooms = chatlog_api.get_chatrooms()
            for name, tid in chatrooms.items():
                if config.name in name or name in config.name:
                    group_id = tid
                    break

        # 最后尝试从数据库获取
        if not group_id and db_fetcher:
            group_id = db_fetcher.get_group_id_by_name(config.name, chatrooms_csv)

        if not group_id:
            print(f"  错误: 未找到群ID")
            continue
        print(f"  群ID: {group_id}")

        # 获取消息 - 根据数据源优先选择
        messages = []
        if use_api and chatlog_api:
            messages = chatlog_api.fetch_messages(group_id, target_date)

        if not messages and db_fetcher:
            messages = db_fetcher.fetch_messages(group_id, target_date)

        print(f"  找到 {len(messages)} 条消息")

        if not messages:
            print(f"  跳过（无消息）")
            continue

        # 分析话题
        print(f"  分析话题...")
        topics = TopicAnalyzer.analyze_topics(messages, top_n=3)
        print(f"  识别出 {len(topics)} 个热门话题")

        # 生成HTML
        output_file = Path(output_dir) / f"{config.name}_{target_date}.html"
        print(f"  生成报告: {output_file}")

        HTMLGenerator.generate_report(
            group_name=config.name,
            date=target_date,
            topics=topics,
            total_messages=len(messages),
            output_path=str(output_file)
        )

    print(f"\n完成! 报告已保存到: {output_dir}")


if __name__ == "__main__":
    main()
