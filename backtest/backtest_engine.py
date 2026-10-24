"""
事件驱动型回测引擎 (Event-Driven Backtesting Engine)
特性：严格规避未来函数、支持滑点与手续费模型、逐日逐K线模拟账户资产与持仓结算
"""
import pandas as pd
import numpy as np
from utils.logger import setup_logger

logger = setup_logger("BacktestEngine")

class EventDrivenBacktester:
    """事件驱动回测引擎"""

    def __init__(self, initial_capital: float = 100000.0, commission_rate: float = 0.0001, slippage_pct: float = 0.0005):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate  # 手续费比例 (默认万一)
        self.slippage_pct = slippage_pct        # 滑点比例 (默认万分之五)
        
        self.positions = {}     # 当前持仓: {symbol: shares}
        self.trades = []        # 历史成交明细
        self.portfolio_history = []  # 每日净值曲线

    def run_backtest(self, price_df: pd.DataFrame, signals_df: pd.DataFrame) -> pd.DataFrame:
        """
        严格按时间序列步进回测：
        - 信号生成在 T 日收盘后 (signals_df)
        - 交易撮合执行在 T+1 日开盘价 (规避未来函数)
        """
        logger.info(f"🚀 开始执行事件驱动回测，初始资本: ${self.initial_capital:,.2f}")
        
        # 按照日期排序
        merged = pd.merge(price_df, signals_df[["timestamp", "symbol", "signal"]], on=["timestamp", "symbol"], how="left")
        merged = merged.sort_values("timestamp").reset_index(drop=True)
        
        symbols = merged["symbol"].unique()
        for s in symbols:
            self.positions[s] = 0.0

        # 获取交易日历
        dates = merged["timestamp"].unique()
        pending_order = None  # 挂起的隔夜订单: (symbol, target_action, date)

        for i, current_date in enumerate(dates):
            day_data = merged[merged["timestamp"] == current_date]
            
            # 1. 优先撮合上一交易日盘后生成的待执行订单 (以今日开盘价成交)
            if pending_order is not None:
                p_sym, p_action = pending_order
                row = day_data[day_data["symbol"] == p_sym]
                if not row.empty:
                    open_price = row["open"].iloc[0]
                    self._execute_order(p_sym, p_action, open_price, current_date)
                pending_order = None

            # 2. 结算今日收盘后的账户总资产与净值
            total_equity = self.cash
            for sym, shares in self.positions.items():
                r = day_data[day_data["symbol"] == sym]
                if not r.empty:
                    close_price = r["close"].iloc[0]
                    total_equity += shares * close_price
            
            self.portfolio_history.append({
                "timestamp": current_date,
                "cash": self.cash,
                "total_equity": total_equity,
                "daily_return": 0.0
            })

            # 3. 盘后接收信号，若有买卖指示，挂起订单在下一交易日开盘成交
            for _, r in day_data.iterrows():
                sig = r["signal"]
                sym = r["symbol"]
                if sig in ["BUY", "SELL"]:
                    pending_order = (sym, sig)

        perf_df = pd.DataFrame(self.portfolio_history)
        if not perf_df.empty:
            perf_df["daily_return"] = perf_df["total_equity"].pct_change().fillna(0.0)
            perf_df["cumulative_return"] = (perf_df["total_equity"] / self.initial_capital) - 1.0
            
        logger.info(f"✅ 回测结束，期末总资产: ${perf_df['total_equity'].iloc[-1]:,.2f}，累计收益率: {perf_df['cumulative_return'].iloc[-1]*100:.2f}%")
        return perf_df

    def _execute_order(self, symbol: str, action: str, price: float, date: str):
        """撮合订单，计算滑点与手续费"""
        current_shares = self.positions.get(symbol, 0.0)

        if action == "BUY" and current_shares == 0:
            # 买入：以包含滑点的价格买入，满仓分配
            exec_price = price * (1.0 + self.slippage_pct)
            available_funds = self.cash * 0.98  # 预留2%安全垫
            shares_to_buy = int(available_funds // exec_price)
            if shares_to_buy > 0:
                cost = shares_to_buy * exec_price
                commission = cost * self.commission_rate
                self.cash -= (cost + commission)
                self.positions[symbol] = shares_to_buy
                self.trades.append({
                    "date": date, "symbol": symbol, "action": "BUY",
                    "price": round(exec_price, 2), "shares": shares_to_buy, "fee": round(commission, 2)
                })
                logger.info(f"[{date}] 成交买入: {symbol} | 股数: {shares_to_buy} | 成交价: ${exec_price:.2f}")

        elif action == "SELL" and current_shares > 0:
            # 卖出：以扣除滑点的价格平仓
            exec_price = price * (1.0 - self.slippage_pct)
            proceeds = current_shares * exec_price
            commission = proceeds * self.commission_rate
            self.cash += (proceeds - commission)
            self.trades.append({
                "date": date, "symbol": symbol, "action": "SELL",
                "price": round(exec_price, 2), "shares": current_shares, "fee": round(commission, 2)
            })
            logger.info(f"[{date}] 成交平仓: {symbol} | 股数: {current_shares} | 成交价: ${exec_price:.2f}")
            self.positions[symbol] = 0.0
