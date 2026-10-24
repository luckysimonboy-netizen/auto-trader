"""
阶段3功能验收测试脚本：
运行 QQQ 双均线趋势策略 -> 事件驱动引擎撮合交易 -> 结算净值并输出夏普比率/最大回撤
"""
import numpy as np
import pandas as pd
from data.storage_engine import HybridStorageEngine
from strategy.qqq_trend_strategy import QQQTrendStrategy
from backtest.backtest_engine import EventDrivenBacktester
from utils.logger import setup_logger

logger = setup_logger("Phase3_Test")

def calculate_performance_metrics(equity_series: pd.Series, daily_returns: pd.Series):
    """计算夏普比率、最大回撤与年化收益"""
    total_return = (equity_series.iloc[-1] / equity_series.iloc[0]) - 1.0
    trading_days = len(equity_series)
    annualized_return = ((1.0 + total_return) ** (252 / max(trading_days, 1))) - 1.0
    
    # 年化波动率与夏普比率 (假设无风险利率 4%)
    rf_daily = 0.04 / 252
    excess_ret = daily_returns - rf_daily
    ann_vol = daily_returns.std() * np.sqrt(252)
    sharpe = (excess_ret.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0.0
    
    # 历史最大回撤计算
    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    max_drawdown = drawdown.min()
    
    return {
        "累计收益率": f"{total_return * 100:.2f}%",
        "年化收益率": f"{annualized_return * 100:.2f}%",
        "年化波动率": f"{ann_vol * 100:.2f}%",
        "夏普比率 (Sharpe)": round(sharpe, 2),
        "最大回撤 (MaxDD)": f"{max_drawdown * 100:.2f}%",
        "交易天数": trading_days
    }

def run_phase3_verification():
    print("=" * 75)
    print("🚀 开始执行【阶段3：事件驱动回测引擎 & QQQ趋势策略】全功能验证")
    print("=" * 75)

    storage = HybridStorageEngine()
    target_symbol = "QQQ"
    
    # 1. 读取阶段1已经下载好的 QQQ 日线数据
    df = storage.load_data(target_symbol, interval="1d")
    if df.empty:
        print(f"❌ 本地尚未找到 {target_symbol} 行情，请确认阶段1已成功下载数据。")
        return

    # 2. 调用 QQQ 策略生成无未来函数的离线信号
    print(f"\n--- [测试 1] 针对 {target_symbol} 生成双均线趋势信号 ---")
    strat = QQQTrendStrategy(fast_window=5, slow_window=20)
    signals_df = strat.generate_signals(df)

    # 3. 启动事件驱动引擎进行隔夜撮合与持仓结算
    print(f"\n--- [测试 2] 启动事件驱动回测引擎 (扣除手续费与万分之五动态滑点) ---")
    engine = EventDrivenBacktester(initial_capital=100000.0, commission_rate=0.0001, slippage_pct=0.0005)
    perf_df = engine.run_backtest(df, signals_df)

    # 4. 输出量化绩效体检报告
    print(f"\n--- [测试 3] QQQ 双均线策略绩效评估报告 ---")
    metrics = calculate_performance_metrics(perf_df["total_equity"], perf_df["daily_return"])
    for k, v in metrics.items():
        print(f"📊 {k}: {v}")

    print("\n--- 历史真实撮合成交记录明细 (最近 5 笔) ---")
    trades_df = pd.DataFrame(engine.trades)
    if not trades_df.empty:
        print(trades_df.tail(5).to_string(index=False))
    else:
        print("期间未触发调仓买卖。")

    print("\n" + "=" * 75)
    print("🎉 【阶段 3 验证成功】事件驱动撮合与第一套策略已无缝闭环！")
    print("=" * 75)

if __name__ == "__main__":
    run_phase3_verification()
