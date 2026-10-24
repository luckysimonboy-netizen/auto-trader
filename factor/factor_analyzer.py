"""
因子分析与评估套件 (Factor Analyzer)
核心能力：Rank IC / Normal IC 计算、IC/IR 分析、分层回测 (Quantile Analysis)、因子相关性矩阵
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from utils.logger import setup_logger

logger = setup_logger("FactorAnalyzer")

class FactorAnalyzer:
    """因子时序与横截面绩效分析器"""

    @staticmethod
    def calculate_ic_series(df_panel: pd.DataFrame, factor_col: str, forward_return_col: str = "target_return_1d") -> pd.DataFrame:
        """
        计算因子的时序 IC (Information Coefficient):
        - Normal IC: Pearson 相关系数
        - Rank IC: Spearman 秩相关系数
        """
        ic_records = []
        for date, group in df_panel.groupby("timestamp"):
            if len(group) < 3:
                continue
            f = group[factor_col]
            r = group[forward_return_col]
            valid_mask = f.notna() & r.notna()
            if valid_mask.sum() < 3:
                continue

            f_valid = f[valid_mask]
            r_valid = r[valid_mask]

            norm_ic = f_valid.corr(r_valid)
            rank_ic, _ = spearmanr(f_valid, r_valid)

            ic_records.append({
                "timestamp": date,
                "normal_ic": norm_ic,
                "rank_ic": rank_ic
            })

        ic_df = pd.DataFrame(ic_records)
        return ic_df

    @classmethod
    def evaluate_ic_metrics(cls, ic_df: pd.DataFrame) -> dict:
        """输出 IC / IR 核心指标"""
        if ic_df.empty:
            return {}

        mean_rank_ic = ic_df["rank_ic"].mean()
        std_rank_ic = ic_df["rank_ic"].std()
        ir = mean_rank_ic / std_rank_ic if std_rank_ic != 0 else 0.0
        ic_pos_ratio = (ic_df["rank_ic"] > 0).mean()

        return {
            "mean_rank_ic": round(float(mean_rank_ic), 4),
            "std_rank_ic": round(float(std_rank_ic), 4),
            "ic_ir": round(float(ir), 4),
            "ic_positive_ratio": round(float(ic_pos_ratio), 4),
            "sample_periods": len(ic_df)
        }

    @staticmethod
    def quantile_layered_backtest(df_panel: pd.DataFrame, factor_col: str, forward_return_col: str = "target_return_1d", n_quantiles: int = 5) -> pd.DataFrame:
        """
        因子分层回测 (Quantile Grouping):
        将全市场在每个截面按因子从低到高分为 Q1 到 Qn 组，计算各组累计收益率与多空利差 (Long-Short)
        """
        records = []
        for date, group in df_panel.groupby("timestamp"):
            sub = group[[factor_col, forward_return_col]].dropna().copy()
            if len(sub) < n_quantiles:
                continue

            # 按因子分位数打标
            try:
                sub["quantile"] = pd.qcut(sub[factor_col].rank(method="first"), q=n_quantiles, labels=[f"Q{i+1}" for i in range(n_quantiles)])
            except Exception:
                continue

            q_ret = sub.groupby("quantile", observed=False)[forward_return_col].mean().to_dict()
            q_ret["timestamp"] = date
            records.append(q_ret)

        res_df = pd.DataFrame(records)
        if not res_df.empty:
            res_df = res_df.sort_values("timestamp").reset_index(drop=True)
            # 计算多空对冲收益 (Q_top - Q_bottom)
            res_df["Long_Short"] = res_df[f"Q{n_quantiles}"] - res_df["Q1"]
        return res_df

    @staticmethod
    def factor_correlation_matrix(df_cross: pd.DataFrame, factor_cols: list[str]) -> pd.DataFrame:
        """计算因子相关性矩阵，识别多重共线性"""
        valid_cols = [c for c in factor_cols if c in df_cross.columns]
        return df_cross[valid_cols].corr(method="spearman").round(4)
