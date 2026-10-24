"""
实时舆情与全球宏观动态监控引擎 (Sentiment & Macro Monitor)
功能：
1. 监控特朗普动态（关税、制裁、贸易战、科技禁令、Truth Social言论）
2. 监控美国本土与全球宏观（美联储FOMC、CPI、非农、利率决议）
3. 自动化情感打分与事件重要性分级 (Low/Medium/High/Extreme)
4. 行业影响标签自动映射 (科技、半导体、能源、金融、消费等)
5. 与风控系统联动：极端事件自动触发全系统暂停开仓/避险
"""
import os
import json
import sqlite3
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger("SentimentMonitor")

class SentimentMacroMonitor:
    """实时舆情与宏观风控联动引擎"""

    def __init__(self, db_path: str = "storage/sentiment_events.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

        # 核心关键词库与关联行业映射
        self.trump_keywords = {
            "关税": {"sector": "Trade/Manufacturing", "default_sentiment": -0.8, "importance": "high"},
            "tariff": {"sector": "Trade/Manufacturing", "default_sentiment": -0.8, "importance": "high"},
            "制裁": {"sector": "Geopolitics/Tech", "default_sentiment": -0.7, "importance": "high"},
            "sanction": {"sector": "Geopolitics/Tech", "default_sentiment": -0.7, "importance": "high"},
            "贸易战": {"sector": "Broad_Market", "default_sentiment": -0.9, "importance": "extreme"},
            "trade war": {"sector": "Broad_Market", "default_sentiment": -0.9, "importance": "extreme"},
            "科技禁令": {"sector": "Information Technology", "default_sentiment": -0.85, "importance": "high"},
            "芯片限制": {"sector": "Semiconductors", "default_sentiment": -0.8, "importance": "high"},
            "减税": {"sector": "Broad_Market", "default_sentiment": 0.8, "importance": "high"},
            "tax cut": {"sector": "Broad_Market", "default_sentiment": 0.8, "importance": "high"}
        }

        self.macro_keywords = {
            "加息": {"sector": "Financials/Growth", "default_sentiment": -0.6, "importance": "high"},
            "降息": {"sector": "Growth/Broad_Market", "default_sentiment": 0.7, "importance": "high"},
            "rate cut": {"sector": "Growth/Broad_Market", "default_sentiment": 0.7, "importance": "high"},
            "CPI超预期": {"sector": "Broad_Market", "default_sentiment": -0.75, "importance": "high"},
            "非农超预期": {"sector": "Broad_Market", "default_sentiment": -0.5, "importance": "medium"},
            "FOMC": {"sector": "Broad_Market", "default_sentiment": 0.0, "importance": "high"}
        }

    def _init_db(self):
        """初始化舆情事件持久化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sentiment_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    source TEXT,
                    headline TEXT,
                    matched_keyword TEXT,
                    target_sector TEXT,
                    sentiment_score REAL,
                    importance_level TEXT,
                    risk_action_triggered TEXT
                )
            """)
            conn.commit()

    def analyze_news_item(self, headline: str, source: str = "RSS_Feed") -> dict | None:
        """
        分析单条新闻或动态文本：
        提取关键词、计算情感偏向、判断重要性，并决定是否触发风控动作
        """
        lower_head = headline.lower()
        matched = None
        info = None

        # 1. 优先扫描特朗普专属词库
        for kw, meta in self.trump_keywords.items():
            if kw.lower() in lower_head:
                matched = kw
                info = meta
                break

        # 2. 扫描宏观经济词库
        if not matched:
            for kw, meta in self.macro_keywords.items():
                if kw.lower() in lower_head:
                    matched = kw
                    info = meta
                    break

        if not matched:
            return None  # 无关普通新闻，直接降噪忽略

        score = info["default_sentiment"]
        level = info["importance"]
        sector = info["sector"]

        # 3. 风控联动判断
        risk_action = "NONE"
        if level == "extreme" or score <= -0.8:
            risk_action = "PAUSE_BUYING (重大黑天鹅/极端利空，全系统暂停开仓)"
            logger.error(f"🚨 [极端舆情风控触发] 命中重大词汇 [{matched}]！动作: {risk_action}")
        elif level == "high" and score < -0.5:
            risk_action = "WARN_REDUCE (高级风险，建议关注对冲或逢高减仓)"
            logger.warning(f"⚠️ [高风险舆情预警] 命中敏感词汇 [{matched}]！动作: {risk_action}")
        elif score > 0.6:
            risk_action = "BULLISH_SIGNAL (强利好刺激，可提升多头置信度)"
            logger.info(f"✨ [重大利好舆情] 命中利好词汇 [{matched}]！")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        event_id = f"EVT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(headline) % 10000}"

        event_data = {
            "event_id": event_id,
            "timestamp": now_str,
            "source": source,
            "headline": headline,
            "matched_keyword": matched,
            "target_sector": sector,
            "sentiment_score": score,
            "importance_level": level,
            "risk_action_triggered": risk_action
        }

        # 4. 持久化归档到 SQLite
        self._save_event(event_data)
        return event_data

    def _save_event(self, event: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sentiment_events
                (event_id, timestamp, source, headline, matched_keyword, target_sector, sentiment_score, importance_level, risk_action_triggered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event["event_id"], event["timestamp"], event["source"], event["headline"],
                event["matched_keyword"], event["target_sector"], event["sentiment_score"],
                event["importance_level"], event["risk_action_triggered"]
            ))
            conn.commit()

    def get_latest_risk_status(self) -> tuple[bool, str]:
        """
        供交易网关和回测引擎查询：当前是否有活跃的极端舆情禁令
        返回: (是否允许开仓, 原因描述)
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT headline, risk_action_triggered FROM sentiment_events 
                WHERE risk_action_triggered LIKE 'PAUSE_BUYING%'
                ORDER BY timestamp DESC LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                return False, f"受到突发舆情封锁: 【{row[0]}】 (动作: {row[1]})"
        return True, "舆情面平稳，允许正常交易"
