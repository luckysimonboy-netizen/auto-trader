import pandas as pd
from utils.logger import setup_logger

logger = setup_logger("DataCleaner")

class DataCleanerAndAdjuster:
    """清洗异常价格并实现可追溯复权"""
    
    @staticmethod
    def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        initial_len = len(df)
        df = df.drop_duplicates(subset=["symbol", "timestamp", "interval"]).sort_values("timestamp").reset_index(drop=True)
        
        # 价格包络与有效性校验 (High >= Open/Close >= Low)
        valid_mask = (
            (df["volume"] >= 0) & (df["close"] > 0) &
            (df["high"] >= df["low"]) &
            (df["high"] >= df["close"]) &
            (df["high"] >= df["open"]) &
            (df["low"] <= df["close"]) &
            (df["low"] <= df["open"])
        )
        df = df[valid_mask].copy().reset_index(drop=True)
        
        dropped = initial_len - len(df)
        if dropped > 0:
            logger.info(f"[{df['symbol'].iloc[0]}] 清洗剔除无效/毛刺数据 {dropped} 条")
        return df

    @staticmethod
    def apply_adjustment(df: pd.DataFrame, adjust_type: str = "qfq") -> pd.DataFrame:
        if df.empty:
            return df
        df = df.sort_values("timestamp").reset_index(drop=True).copy()
        
        # 拆股与分红因子的累积连乘
        split_ratio = df["splits"].replace(0.0, 1.0)
        prev_close = df["close"].shift(1).fillna(df["close"])
        div_factor = (1.0 - (df["dividends"] / prev_close)).clip(lower=0.01, upper=1.0)
        
        hfq_mult = (split_ratio / div_factor).cumprod()
        qfq_mult = hfq_mult / hfq_mult.iloc[-1]
        
        df["qfq_factor"] = qfq_mult
        df["hfq_factor"] = hfq_mult
        df["raw_close"] = df["close"]
        
        factor = qfq_mult if adjust_type == "qfq" else (hfq_mult if adjust_type == "hfq" else 1.0)
        for col in ["open", "high", "low", "close"]:
            df[col] = (df[col] * factor).round(4)
            
        return df
