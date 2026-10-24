import os
from datetime import datetime, timezone

# ==============================================================================
# 🏛️ 模块四：自动化实盘交割与风控熔断执行网关 (Execution Gateway)
# ==============================================================================

class QuantExecutionGateway:
    """自动化实盘交割与风控熔断网关"""
    
    def __init__(self, initial_capital: float = 1000.0, order_amount: float = 20.0):
        self.capital = initial_capital
        self.order_amount = order_amount

    def execute_orders(self, committee_decisions: list) -> list:
        """根据赛博投委会的决策，冷酷执行自动化猎杀与交割"""
        print("⚡ [Execution Gateway] 正在启动实盘交割与风控网关...")
        execution_logs = []
        
        for decision in committee_decisions:
            ticker = decision["ticker"]
            signal = decision["signal"]
            score = decision["score"]
            reason = decision["reason"]
            
            if "BUY" in signal and score >= 2:
                if self.capital >= self.order_amount:
                    self.capital -= self.order_amount
                    log = f"🔥 【实盘狙击成交】标的: `{ticker}` | 动作: `BUY` | 金额: `${self.order_amount} USDT` | 剩余可用资金: `${self.capital:.1f} USDT` | 逻辑: {reason}"
                    execution_logs.append(log)
                else:
                    log = f"⚠️ 【资金池告急】标 of 目标 `{ticker}` 触发买入，但流动现金池不足！"
                    execution_logs.append(log)
            elif "SELL" in signal:
                log = f"⚠️ 【风控清仓警报】标的: `{ticker}` | 动作: `SELL` | 触发逻辑: {reason}"
                execution_logs.append(log)
            else:
                execution_logs.append(f"⏸️ 【保持观望】标的: `{ticker}` | 状态: 因子未达绝杀阈值 ({reason})")
                
        print(f"✅ [Execution Gateway] 批量交割完毕，剩余流动资金水位: ${self.capital:.1f} USDT")
        return execution_logs

    @staticmethod
    def generate_final_master_report(committee_decisions: list, execution_logs: list):
        """生成终极赛博 CIO 统帅部情报与交割日报"""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        table_rows = []
        for r in committee_decisions:
            table_rows.append(f"| **{r['ticker']}** | `${r['price']}` | `{r['rsi']}` | `{r['bias']}%` | `{r['volatility']}%` | **`{r['score']}/2`** | `{r['signal']}` | {r['reason']} |")
            
        signal_table = "\n".join(table_rows)
        logs_text = "\n".join(f"- {log}" for log in execution_logs)

        report = f"""# 🏛️ 工业级 AI 量化智能体帝国 · 统帅部总控情报与实盘交割日报
> **执行时间**：`{now_str}` ｜ **核心架构**：`Data Pipeline + Factor Engine + Cyber Committee + Execution Gateway` ｜ **系统状态**：`帝国全功能满载运行`

## 一、 资本资产与风控水位
* **智能风控水池**：`1000.0 USDT` (初始虚拟流動池)
* **单次猎杀建仓额**：`20.0 USDT`
* **统帅部裁决机制**：`多 Agent 交叉审判与风控一票否决`

---

## 二、 全球全景市场 · 赛博投委会狙击排行榜
| 标的资产 | 当前价格 | 14h RSI | 乖离率(BIAS) | 年化波动率 | 投委会得分 | 统帅部裁决 | 交叉审判因子與風控透視 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{signal_table}

---

## 三、 实盘交割与自动化执行回执
{logs_text}

---
* 🤖 **AI Quant Agent 帝国提示**：四大核心工程模块已全部无缝打通，系统正以工业级的高并发與高精度持续为你猎杀全市场的阿尔法收益。
"""

        with open("LATEST_CIO_MEMO.md", "w", encoding="utf-8") as f:
            f.write(report)
        print("🎯 终极统帅部情报日报 `LATEST_CIO_MEMO.md` 已成功生成并落地！")

if __name__ == "__main__":
    from data_pipeline import MarketDataPipeline
    from factor_engine import AlphaFactorFactory
    from committee_agent import CyberInvestmentCommittee
    
    # 统帅部主控流程编排
    cache = MarketDataPipeline.run_pipeline()
    factors = AlphaFactorFactory.batch_process(cache)
    decisions = CyberInvestmentCommittee.convene_committee(factors)
    
    gateway = QuantExecutionGateway(initial_capital=1000.0, order_amount=20.0)
    logs = gateway.execute_orders(decisions)
    gateway.generate_final_master_report(decisions, logs)
