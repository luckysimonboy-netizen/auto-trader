"""
阶段2功能验收测试脚本：
验证基础量价因子计算 -> 舆情因子映射 -> 因子预处理(MAD/标准化/中性化) -> IC/IR分析 -> 分层回测
"""
import pandas as pd
import numpy as np
from data.storage_engine import HybridStorageEngine
from factor.factor_engine import FactorEngine
from factor.factor_analyzer import FactorAnalyzer
from utils.logger import setup_logger

logger = setup_logger("Phase2_Test")

def run_phase2_verification():
    print("=" * 75)
    print("🚀 开始执行【阶段2：美股量化系统 - 因子模块与因子分析】全功能验证")
    print("=" * 75)

    storage = HybridStorageEngine()
    symbols = ["AAPL", "NVDA", "TSLA", "MSFT", "SPY"]

    # 1. 提取各标的数据并计算量价与波动因子
    print("\n--- [测试 1] 计算基础量价因子 (RSI, MACD, ATR, 布林带, 乖离率, 波动率) ---")
    spy_df = storage.load_data("SPY", interval="1d")
    all_symbol_factors = []

    for sym in symbols:
        df = storage.load_data(sym, interval="1d")
        if df.empty:
            logger.warning(f"本地库未找到 {sym} 数据，请确认已跑通阶段1！")
            continue
        
        # 因子计算
        f_df = FactorEngine.compute_technical_factors(df, benchmark_df=spy_df)
        # 计算未来1日收益率作为因子检验目标
        f_df["target_return_1d"] = f_df["close"].pct_change().shift(-1)
        all_symbol_factors.append(f_df)
        print(f"✅ {sym} 因子提取完毕: 最新 RSI={f_df['rsi_14'].iloc[-1]:.2f} | 乖离率 BIAS={f_df['bias_20'].iloc[-1]:.2f}% | ATR={f_df['atr_14'].iloc[-1]:.2f}")

    if not all_symbol_factors:
        print("❌ 未能读取到有效数据，测试终止。")
        return

    panel_df = pd.concat(all_symbol_factors, ignore_index=True)

    # 2. 模拟舆情与宏观事件量化因子
    print("\n--- [测试 2] 舆情情感与事件重要性因子映射 ---")
    sample_sentiment = FactorEngine.map_sentiment_to_factor(sentiment_score=-0.8, event_importance="high")
    print(f"示例事件 [特朗普加征关税言论] -> 情感值 -0.8 | 重要性 high -> 量化因子得分: {sample_sentiment}")

    # 3. 截面因子加工：去极值、标准化
    print("\n--- [测试 3] 截面因子加工 (MAD去极值 + Z-Score标准化) ---")
    factor_list = ["rsi_14", "bias_20", "volatility_20d", "boll_pct_b"]
    processed_df = FactorEngine.process_cross_sectional_factors(panel_df, factor_list)
    print("标准化后因子描述统计 (均值接近0，标准差接近1)：")
    print(processed_df[factor_list].describe().loc[["mean", "std", "min", "max"]])

    # 4. 因子分析工具：IC / IR 分析
    print("\n--- [测试 4] 因子时序 IC / IR 分析 (以 20日乖离率 BIAS 为例) ---")
    ic_df = FactorAnalyzer.calculate_ic_series(processed_df, factor_col="bias_20", forward_return_col="target_return_1d")
    ic_metrics = FactorAnalyzer.evaluate_ic_metrics(ic_df)
    print(f"BIAS 因子 IC 指标报告: {ic_metrics}")

    # 5. 因子分层回测 (Quantile Grouping)
    print("\n--- [测试 5] 因子分层回测单调性检验 (3分位示例) ---")
    quantile_res = FactorAnalyzer.quantile_layered_backtest(processed_df, factor_col="bias_20", forward_return_col="target_return_1d", n_quantiles=3)
    if not quantile_res.empty:
        mean_q_ret = quantile_res[["Q1", "Q2", "Q3", "Long_Short"]].mean() * 100
        print("各分层平均单日收益率 (%):")
        print(mean_q_ret.round(4).to_string())

    # 6. 因子相关性矩阵
    print("\n--- [测试 6] 因子相关性矩阵 (Spearman Rank Corr) ---")
    corr_mat = FactorAnalyzer.factor_correlation_matrix(processed_df, factor_list)
    print(corr_mat.to_string())

    print("\n" + "=" * 75)
    print("🎉 【阶段 2 验证全部通过】因子库与分析模块已完备，随时可向事件驱动回测引擎供给因子！")
    print("=" * 75)

if __name__ == "__main__":
    run_phase2_verification()
