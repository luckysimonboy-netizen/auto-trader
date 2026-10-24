"""
参数寻优与防过拟合检验引擎 (Optimizer & Walk-Forward Validation)
核心功能：网格搜索 (Grid Search)、严格时序样本切割、样本外(Out-of-Sample)验证、参数敏感度衰减分析
"""
import pandas as pd
import numpy as np
from strategy.qqq_trend_strategy import QQQTrendStrategy
from backtest.backtest_engine import EventDrivenBacktester
from utils.logger import setup_logger

logger = setup_logger("Optimizer")

class StrategyOptimizer:
    """策略参数寻优与过拟合防范器"""

    def __init__(self, price_df: pd.DataFrame, initial_capital: float = 100000.0):
        self.df = price_df.sort_values("timestamp").reset_index(drop=True)
        self.initial_capital = initial_capital

    def split_train_test(self, train_ratio: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        严格按时间序列切分训练集 (样本内) 与 测试集 (样本外)
        禁止打乱时序，严防未来信息泄露
        """
        split_idx = int(len(self.df) * train_ratio)
        train_df = self.df.iloc[:split_idx].copy().reset_index(drop=True)
        test_df = self.df.iloc[split_idx:].copy().reset_index(drop=True)
        
        logger.info(f"时序切分完成: 样本内(训练) {len(train_df)} 根K线 | 样本外(验证) {len(test_df)} 根K线")
        return train_df, test_df

    def grid_search(self, train_df: pd.DataFrame, fast_range: list[int], slow_range: list[int]) -> pd.DataFrame:
        """
        网格搜索：遍历快慢均线参数组合，寻找样本内最佳夏普比率
        """
        results = []
        logger.info(f"开始网格搜索，总计测试 {len(fast_range) * len(slow_range)} 组参数...")

        for fast in fast_range:
            for slow in slow_range:
                if fast >= slow:
                    continue  # 快线必须小于慢线

                # 1. 生成该参数下的信号
                strat = QQQTrendStrategy(fast_window=fast, slow_window=slow)
                signals_df = strat.generate_signals(train_df)

                # 2. 回测并结算
                engine = EventDrivenBacktester(initial_capital=self.initial_capital)
                perf_df = engine.run_backtest(train_df, signals_df)

                # 3. 计算绩效指标
                daily_ret = perf_df["daily_return"]
                total_ret = perf_df["cumulative_return"].iloc[-1]
                ann_vol = daily_ret.std() * np.sqrt(252)
                rf_daily = 0.04 / 252
                excess = daily_ret - rf_daily
                sharpe = (excess.mean() / daily_ret.std()) * np.sqrt(252) if daily_ret.std() > 0 else -99.0

                results.append({
                    "fast_window": fast,
                    "slow_window": slow,
                    "in_sample_return": round(float(total_ret * 100), 2),
                    "in_sample_sharpe": round(float(sharpe), 2),
                    "trades_count": len(engine.trades)
                })

        res_df = pd.DataFrame(results)
        if not res_df.empty:
            res_df = res_df.sort_values("in_sample_sharpe", ascending=False).reset_index(drop=True)
        return res_df

    def validate_out_of_sample(self, test_df: pd.DataFrame, best_fast: int, best_slow: int) -> dict:
        """
        将样本内选出的最优参数，直接放进从未见过的【样本外数据】进行残酷盲测
        """
        logger.info(f"正在对最优参数 (快线={best_fast}, 慢线={best_slow}) 进行样本外盲测...")
        strat = QQQTrendStrategy(fast_window=best_fast, slow_window=best_slow)
        signals_df = strat.generate_signals(test_df)

        engine = EventDrivenBacktester(initial_capital=self.initial_capital)
        perf_df = engine.run_backtest(test_df, signals_df)

        daily_ret = perf_df["daily_return"]
        total_ret = perf_df["cumulative_return"].iloc[-1]
        ann_vol = daily_ret.std() * np.sqrt(252)
        rf_daily = 0.04 / 252
        excess = daily_ret - rf_daily
        sharpe = (excess.mean() / daily_ret.std()) * np.sqrt(252) if daily_ret.std() > 0 else 0.0

        cummax = perf_df["total_equity"].cummax()
        max_dd = ((perf_df["total_equity"] - cummax) / cummax).min()

        return {
            "best_fast": best_fast,
            "best_slow": best_slow,
            "out_of_sample_return": f"{total_ret * 100:.2f}%",
            "out_of_sample_sharpe": round(float(sharpe), 2),
            "out_of_sample_max_dd": f"{max_dd * 100:.2f}%",
            "out_of_sample_trades": len(engine.trades)
        }
