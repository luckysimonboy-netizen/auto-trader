"""
模拟盘实盘跟踪与状态断点续跑模块 (Paper Trader)
功能：本地持久化账户状态、对接风控前置校验、生成每日模拟持仓与净值记录
"""
import os
import json
import pandas as pd
from datetime import datetime
from risk.risk_manager import RiskManager
from utils.logger import setup_logger

logger = setup_logger("PaperTrader")

class PaperTrader:
    """具备断点续跑能力的模拟盘引擎"""

    def __init__(self, state_file: str = "storage/paper_account.json", initial_capital: float = 20000.0):
        self.state_file = state_file
        self.risk_manager = RiskManager()
        self.account_state = self._load_or_init_state(initial_capital)

    def _load_or_init_state(self, initial_capital: float) -> dict:
        """从本地 JSON 文件读取持久化状态，实现断点续跑"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    logger.info(f"💾 检测到本地模拟盘历史存档，成功读取断点状态！当前总资产: ${state.get('total_equity', 0):,.2f}")
                    return state
            except Exception as e:
                logger.error(f"读取本地存档失败，重新初始化: {e}")

        # 若无本地存档，则初始化
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        init_state = {
            "cash": initial_capital,
            "total_equity": initial_capital,
            "positions": {},  # {symbol: {"shares": 10, "avg_cost": 150.0}}
            "trade_history": [],
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self._save_state(init_state)
        logger.info(f"✨ 初始模拟盘建立完毕，初始资金: ${initial_capital:,.2f}")
        return init_state

    def _save_state(self, state: dict):
        """持久化保存账户状态到本地"""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)

    def execute_signal(self, symbol: str, signal: str, current_price: float, current_date: str, spy_drop: float = 0.0):
        """
        前置过风控并执行模拟盘下单
        """
        # 1. 前置风控校验 1：熔断检查
        pass_cb, cb_msg = self.risk_manager.check_circuit_breaker(spy_drop)
        if not pass_cb:
            logger.warning(f"订单被熔断拦截: {cb_msg}")
            return

        # 2. 前置风控校验 2：账户回撤检查
        pass_dd, dd_msg = self.risk_manager.check_account_drawdown(self.account_state["total_equity"])
        if not pass_dd:
            logger.error(f"触发清仓风控，停止下单: {dd_msg}")
            return

        cash = self.account_state["cash"]
        positions = self.account_state["positions"]

        # 执行买入信号
        if signal == "BUY":
            target_amount = self.account_state["total_equity"] * 0.15  # 计划买入15%仓位
            
            # 前置风控校验 3：单标的仓位上限检查
            pass_pos, pos_msg = self.risk_manager.check_position_limit(target_amount, self.account_state["total_equity"], symbol)
            if not pass_pos:
                logger.warning(pos_msg)
                return

            if cash >= target_amount:
                shares = int(target_amount // current_price)
                if shares > 0:
                    cost = shares * current_price
                    self.account_state["cash"] -= cost
                    
                    # 记录持仓
                    current_shares = positions.get(symbol, {}).get("shares", 0)
                    positions[symbol] = {
                        "shares": current_shares + shares,
                        "avg_cost": current_price
                    }
                    self.account_state["trade_history"].append({
                        "date": current_date, "symbol": symbol, "action": "BUY",
                        "price": current_price, "shares": shares
                    })
                    logger.info(f"✅ [模拟盘成交] 标的: {symbol} | 买入: {shares} 股 | 成交价: ${current_price:.2f}")

        # 执行卖出信号
        elif signal == "SELL":
            if symbol in positions and positions[symbol]["shares"] > 0:
                shares_to_sell = positions[symbol]["shares"]
                proceeds = shares_to_sell * current_price
                self.account_state["cash"] += proceeds
                del positions[symbol]
                self.account_state["trade_history"].append({
                    "date": current_date, "symbol": symbol, "action": "SELL",
                    "price": current_price, "shares": shares_to_sell
                })
                logger.info(f"✅ [模拟盘平仓] 标的: {symbol} | 平仓: {shares_to_sell} 股 | 成交价: ${current_price:.2f}")

        # 更新当前总资产并保存
        self._update_equity(current_price_map={symbol: current_price})
        self._save_state(self.account_state)

    def _update_equity(self, current_price_map: dict):
        """结算当前净值"""
        equity = self.account_state["cash"]
        for sym, pos in self.account_state["positions"].items():
            price = current_price_map.get(sym, pos["avg_cost"])
            equity += pos["shares"] * price
        self.account_state["total_equity"] = equity
        self.account_state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
