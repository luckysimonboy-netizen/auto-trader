"""
策略2：标普500截面多因子打分选股策略 (融入实时舆情与宏观因子)
- 股票池：标普500核心标的 (AAPL, NVDA, TSLA, MSFT, SPY 等)
- 因子体系：短期乖离率(反转)、RSI、波动率惩罚 + 舆情利好加分
- 调仓规则：定期截面排序，优选 TOP 标的构建组合
"""
import pandas as pd
import numpy as np
from factor.factor_engine import FactorEngine
from sentiment.sentiment_monitor import SentimentMacroMonitor
from utils.logger import setup_logger

logger = setup_logger("MultiFactorStrategy")

class SP500MultiFactorStrategy:
    """标普500多因子选股策略"""

    def __init__(self, top_n: int = 3, use_sentiment: bool = True):
        self.top_n = top_n
        self.use_sentiment = use_sentiment
        self.sentiment_monitor = SentimentMacroMonitor()

    def generate_portfolio_signals(self, market_data_dict: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        在横截面上综合打分并挑选最优组合
        """
        all_scores = []
        sentiment_allowed, sent_reason = self.sentiment_monitor.get_latest_risk_status()

        for symbol, df in market_data_dict.items():
            if df.empty or len(df) < 30:
                continue

            # 1. 计算技术因子
            factors_df = FactorEngine.compute_technical_factors(df)
            latest = factors_df.iloc[-1]

            # 因子基础分计算：
            # - 乖离率超跌得分 (负得越多，反弹潜力越大，给正分)
            bias_score = -float(latest.get("bias_20", 0.0)) * 0.5
            # - RSI 中性偏强加分 (40~60 稳健区间)
            rsi = float(latest.get("rsi_14", 50.0))
            rsi_score = (50.0 - abs(rsi - 50.0)) * 0.1
            # - 低波动奖励 (波动率越低加分越高)
            vol = float(latest.get("volatility_20d", 0.3))
            vol_penalty = -vol * 10.0

            total_score = bias_score + rsi_score + vol_penalty

            # 2. 融入舆情因子作为加分/扣分项
            if self.use_sentiment and not sentiment_allowed:
                total_score -= 5.0  # 全局大盘舆情利空时施加防守惩罚

            all_scores.append({
                "symbol": symbol,
                "timestamp": latest["timestamp"],
                "close": latest["close"],
                "bias_20": round(float(latest.get("bias_20", 0.0)), 2),
                "rsi_14": round(rsi, 2),
                "volatility": round(vol, 2),
                "composite_score": round(total_score, 2)
            })

        score_df = pd.DataFrame(all_scores)
        if score_df.empty:
            return pd.DataFrame()

        # 3. 按综合得分降序排列，优选 TOP N
        score_df = score_df.sort_values("composite_score", ascending=False).reset_index(drop=True)
        score_df["selected"] = False
        score_df.loc[:self.top_n - 1, "selected"] = True

        logger.info(f"多因子截面打分完成，本期精选标的: {score_df[score_df['selected']]['symbol'].tolist()}")
        return score_df
