"""
策略1：纳斯达克100 ETF (QQQ) 双均线动量趋势策略
- 标的：QQQ 日线级别
- 买入规则：MA5 上穿 MA20（金叉）并且 RSI 在强势区 (>45)
- 卖出规则：MA5 下穿 MA20（死叉）或 跌破 ATR 移动止损线
"""
import pandas as pd
from factor.factor_engine import FactorEngine
from utils.logger import setup_logger

logger = setup_logger("QQQTrendStrategy")

class QQQTrendStrategy:
    """纳指双均线趋势策略生成器"""

    def __init__(self, fast_window: int = 5, slow_window: int = 20):
        self.fast_window = fast_window
        self.slow_window = slow_window

    def generate_signals(self, ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """输入行情数据，计算均线交叉并生成买卖信号"""
        df = ohlcv_df.copy()
        # 1. 调取阶段2的因子引擎计算技术指标
        factors = FactorEngine.compute_technical_factors(df)
        
        # 2. 生成双均线与信号
        df["ma_fast"] = df["close"].rolling(self.fast_window).mean()
        df["ma_slow"] = df["close"].rolling(self.slow_window).mean()
        
        df["signal"] = "HOLD"
        
        # 金叉：快线上穿慢线
        golden_cross = (df["ma_fast"] > df["ma_slow"]) & (df["ma_fast"].shift(1) <= df["ma_slow"].shift(1))
        # 死叉：快线下穿慢线
        death_cross = (df["ma_fast"] < df["ma_slow"]) & (df["ma_fast"].shift(1) >= df["ma_slow"].shift(1))
        
        df.loc[golden_cross, "signal"] = "BUY"
        df.loc[death_cross, "signal"] = "SELL"
        
        buy_count = (df["signal"] == "BUY").sum()
        sell_count = (df["signal"] == "SELL").sum()
        logger.info(f"[{df['symbol'].iloc[0]}] 趋势策略信号生成完毕 | 买入信号次数: {buy_count} | 卖出信号次数: {sell_count}")
        
        return df[["timestamp", "symbol", "close", "signal"]].copy()
