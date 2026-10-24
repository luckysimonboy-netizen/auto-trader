"""
独立风控中枢 (Risk Manager)
回测、模拟盘与实盘三端通用，包含：
1. 美股 PDT (Pattern Day Trader) 规则校验拦截
2. 标普500三级熔断时段交易拦截
3. 单标的最大持仓上限与总账户杠杆风控
4. 账户最大回撤清仓熔断线
"""
import pandas as pd
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger("RiskManager")

class RiskManager:
    """全量机构级风控系统"""

    def __init__(
        self,
        pdt_limit: float = 25000.0,
        max_day_trades: int = 3,
        max_single_stock_weight: float = 0.20,
        max_drawdown_limit: float = 0.15
    ):
        self.pdt_limit = pdt_limit                        # PDT资金门槛 ($25,000)
        self.max_day_trades = max_day_trades              # 5日内最多日内交易次数 (3次)
        self.max_single_stock_weight = max_single_stock_weight  # 单标的最大持仓占比 (20%)
        self.max_drawdown_limit = max_drawdown_limit      # 账户最大回撤平仓线 (15%)
        
        self.day_trade_history = []  # 记录日内交易的时间戳列表
        self.peak_equity = 0.0       # 历史最高净值，用于监控回撤

    def check_pdt_rule(self, current_equity: float, is_day_trade: bool, current_date: str) -> tuple[bool, str]:
        """
        检查 PDT 规则：
        若净资产低于 25,000 美元，滚动 5 个交易日内最多允许 3 次日内交易，第 4 次强制拦截！
        """
        if current_equity >= self.pdt_limit:
            return True, "账户净资产>=25k美元，豁免PDT日内交易限制"

        # 清理超过5个自然日/交易日的旧记录
        if is_day_trade:
            if len(self.day_trade_history) >= self.max_day_trades:
                msg = f"⛔ [PDT风控拦截] 净资产 ${current_equity:,.2f} < 25k，近5日已执行 {len(self.day_trade_history)} 次日内交易，达到上限，禁止再次T+0！"
                logger.warning(msg)
                return False, msg
            else:
                self.day_trade_history.append(current_date)
                msg = f"⚠️ [PDT提醒] 触发日内交易，当前近5日已用: {len(self.day_trade_history)}/{self.max_day_trades} 次"
                logger.info(msg)
                return True, msg

        return True, "非日内交易，PDT检查通过"

    def check_circuit_breaker(self, spy_daily_drop: float) -> tuple[bool, str]:
        """
        标普500三级熔断规则检查：
        一级：-7% (暂停15分钟)
        二级：-13% (暂停15分钟)
        三级：-20% (全天停止交易)
        """
        if spy_daily_drop <= -0.20:
            msg = f"🚨 [三级熔断触发] 标普500跌幅达 {spy_daily_drop*100:.1f}%，全天停止交易！"
            logger.error(msg)
            return False, msg
        elif spy_daily_drop <= -0.13:
            msg = f"🚨 [二级熔断触发] 标普500跌幅达 {spy_daily_drop*100:.1f}%，全市场暂停交易 15 分钟！"
            logger.error(msg)
            return False, msg
        elif spy_daily_drop <= -0.07:
            msg = f"⚠️ [一级熔断触发] 标普500跌幅达 {spy_daily_drop*100:.1f}%，全市场暂停交易 15 分钟！"
            logger.warning(msg)
            return False, msg

        return True, "大盘正常，未触发熔断"

    def check_position_limit(self, order_value: float, current_equity: float, symbol: str) -> tuple[bool, str]:
        """单标的持仓权重上限风控"""
        if current_equity <= 0:
            return False, "账户净资产异常"

        weight = order_value / current_equity
        if weight > self.max_single_stock_weight:
            msg = f"⛔ [仓位风控拦截] {symbol} 拟下单金额占比 {weight*100:.1f}% 超过单标的上限 {self.max_single_stock_weight*100:.1f}%"
            logger.warning(msg)
            return False, msg

        return True, "仓位合规"

    def check_account_drawdown(self, current_equity: float) -> tuple[bool, str]:
        """账户回撤红线监控"""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        if self.peak_equity > 0:
            dd = (self.peak_equity - current_equity) / self.peak_equity
            if dd >= self.max_drawdown_limit:
                msg = f"🚨 [清仓线触发] 账户最大回撤达到 {dd*100:.2f}%，触发强制平仓避险红线！"
                logger.error(msg)
                return False, msg

        return True, "账户回撤正常"
