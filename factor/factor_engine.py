"""
因子计算与特征工程工厂 (Factor Engine)
涵盖：量价因子、波动因子、舆情/宏观因子、去极值(MAD)、标准化(Z-Score)、行业/市值中性化
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from utils.logger import setup_logger

logger = setup_logger("FactorEngine")

class FactorEngine:
    """通用因子计算与预处理管道"""

    # ==========================
    # 1. 基础量价与波动因子计算
    # ==========================
    @staticmethod
    def compute_technical_factors(df: pd.DataFrame, benchmark_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        输入单标的OHLCV数据，计算基础量价与波动因子
        """
        if df.empty or len(df) < 30:
            return pd.DataFrame()

        df = df.sort_values("timestamp").reset_index(drop=True).copy()
        c = df["close"]
        h = df["high"]
        l = df["low"]
        v = df["volume"]

        # 1. 均线与乖离率 (MA & BIAS)
        df["ma_5"] = c.rolling(5).mean()
        df["ma_20"] = c.rolling(20).mean()
        df["ma_60"] = c.rolling(60).mean()
        df["bias_20"] = ((c - df["ma_20"]) / df["ma_20"]) * 100

        # 2. RSI (14周期 Wilder 平滑)
        delta = c.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi_14"] = 100 - (100 / (1 + rs))

        # 3. MACD (12, 26, 9)
        ema_12 = c.ewm(span=12, adjust=False).mean()
        ema_26 = c.ewm(span=26, adjust=False).mean()
        df["macd_dif"] = ema_12 - ema_26
        df["macd_dea"] = df["macd_dif"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = (df["macd_dif"] - df["macd_dea"]) * 2

        # 4. ATR (真实波幅) 与 布林带 (%B, BandWidth)
        tr1 = h - l
        tr2 = (h - c.shift(1)).abs()
        tr3 = (l - c.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr_14"] = tr.rolling(14).mean()

        std_20 = c.rolling(20).std()
        df["boll_mid"] = df["ma_20"]
        df["boll_upper"] = df["boll_mid"] + 2 * std_20
        df["boll_lower"] = df["boll_mid"] - 2 * std_20
        df["boll_pct_b"] = (c - df["boll_lower"]) / (df["boll_upper"] - df["boll_lower"]).replace(0, np.nan)
        df["boll_width"] = (df["boll_upper"] - df["boll_lower"]) / df["boll_mid"]

        # 5. 年化历史波动率与量比
        df["volatility_20d"] = c.pct_change().rolling(20).std() * np.sqrt(252)
        vol_ma5 = v.shift(1).rolling(5).mean()
        df["volume_ratio"] = v / vol_ma5.replace(0, np.nan)

        # 6. 相对强弱 (RS vs Benchmark)
        if benchmark_df is not None and not benchmark_df.empty:
            bm_merged = pd.merge(df[["timestamp", "close"]], benchmark_df[["timestamp", "close"]], on="timestamp", suffixes=("", "_bm"))
            if not bm_merged.empty:
                rs_series = (bm_merged["close"] / bm_merged["close"].iloc[0]) / (bm_merged["close_bm"] / bm_merged["close_bm"].iloc[0])
                df["relative_strength"] = rs_series
            else:
                df["relative_strength"] = 1.0
        else:
            df["relative_strength"] = 1.0

        return df

    # ==========================
    # 2. 舆情与宏观事件量化映射
    # ==========================
    @staticmethod
    def map_sentiment_to_factor(sentiment_score: float, event_importance: str = "medium") -> float:
        """
        将非结构化舆情事件转化为数值因子：
        sentiment_score: [-1.0, 1.0] 情感倾向
        event_importance: low(0.5), medium(1.0), high(1.8), extreme(3.0) 权重衰减
        """
        weights = {"low": 0.5, "medium": 1.0, "high": 1.8, "extreme": 3.0}
        w = weights.get(event_importance.lower(), 1.0)
        return float(np.clip(sentiment_score * w, -3.0, 3.0))

    # ==========================
    # 3. 因子预处理：去极值、标准化、中性化
    # ==========================
    @staticmethod
    def mad_filter(series: pd.Series, n: float = 3.0) -> pd.Series:
        """
        绝对中位数法去极值 (Median Absolute Deviation, MAD)
        严格优于 3-Sigma 原则，避免离群值拉偏均值与标准差
        """
        med = series.median()
        mad = (series - med).abs().median()
        if mad == 0:
            return series
        upper = med + n * 1.4826 * mad
        lower = med - n * 1.4826 * mad
        return series.clip(lower=lower, upper=upper)

    @staticmethod
    def zscore_standardize(series: pd.Series) -> pd.Series:
        """Z-Score 标准化"""
        std = series.std()
        if std == 0 or np.isnan(std):
            return series - series.mean()
        return (series - series.mean()) / std

    @classmethod
    def process_cross_sectional_factors(cls, cross_df: pd.DataFrame, factor_cols: list[str]) -> pd.DataFrame:
        """
        横截面因子统一加工流水线：
        1. 逐因子 MAD 去极值
        2. 逐因子 Z-Score 标准化
        """
        df = cross_df.copy()
        for col in factor_cols:
            if col in df.columns:
                df[col] = cls.mad_filter(df[col])
                df[col] = cls.zscore_standardize(df[col])
        return df

    @classmethod
    def neutralize_factor(cls, df: pd.DataFrame, factor_col: str, sector_col: str = "gics_sector", cap_col: str = None) -> pd.Series:
        """
        因子中性化（行业中性化 + 可选对数市值中性化）：
        利用多元线性回归 (OLS) 对行业哑变量及市值进行回归，取残差作为中性化因子暴露
        """
        sub_df = df[[factor_col, sector_col]].copy()
        if cap_col and cap_col in df.columns:
            sub_df["ln_cap"] = np.log(df[cap_col].replace(0, np.nan))
        
        # 哑变量处理 (One-Hot)
        x_dummies = pd.get_dummies(sub_df[sector_col], drop_first=True, dtype=float)
        if cap_col and cap_col in df.columns:
            x_mat = pd.concat([x_dummies, sub_df["ln_cap"]], axis=1)
        else:
            x_mat = x_dummies

        x_mat = sm.add_constant(x_mat)
        y = sub_df[factor_col]

        # 拟合并取残差
        valid_idx = y.dropna().index.intersection(x_mat.dropna().index)
        if len(valid_idx) < len(x_mat.columns) + 2:
            return df[factor_col]

        model = sm.OLS(y.loc[valid_idx], x_mat.loc[valid_idx]).fit()
        residuals = model.resid
        
        neutral_series = df[factor_col].copy()
        neutral_series.loc[valid_idx] = residuals
        return cls.zscore_standardize(neutral_series)
