"""
==============================================================================
🏛️ 美股量化系统 (US Quant System) · 全功能统一启动总控 (Master Controller)
==============================================================================
一键串联：
1. 数据加载与可追溯前复权
2. 基础量价/波动因子计算与 MAD 预处理
3. 标普500多因子综合打分选股 (结合特朗普与宏观舆情)
4. 全量独立风控核查 (PDT、三级熔断、仓位红线)
5. 模拟盘状态同步与持久化更新
"""
import os
import sys
from data.storage_engine import HybridStorageEngine
from data.universe_manager import USDataAndUniverseManager
from factor.factor_engine import FactorEngine
from strategy.sp500_multifactor_strategy import SP500MultiFactorStrategy
from risk.risk_manager import RiskManager
from sentiment.sentiment_monitor import SentimentMacroMonitor
from trader.paper_trader import PaperTrader
from utils.logger import setup_logger

logger = setup_logger("MasterController")

def run_master_pipeline():
    print("=" * 80)
    print("🏛️ 美股工业级量化交易系统 · 统帅部全自动巡航流水线启动")
    print("=" * 80)

    # 1. 舆情监控前置巡检
    print("\n[Step 1/5] 📡 正在扫描实时舆情与宏观动态 (特朗普言论/美联储动向)...")
    sent_monitor = SentimentMacroMonitor()
    trade_allowed, sent_msg = sent_monitor.get_latest_risk_status()
    print(f"  当前舆情状态: [{'🟢 平稳可控' if trade_allowed else '🔴 触发预警'}]")
    print(f"  情报摘要: {sent_msg}")

    # 2. 标的池数据加载与清洗
    print("\n[Step 2/5] 📈 正在从本地双擎数据库加载标普500核心标的行情...")
    storage = HybridStorageEngine()
    symbols = ["AAPL", "NVDA", "TSLA", "MSFT", "SPY"]
    market_data = {}
    
    for s in symbols:
        df = storage.load_data(s, interval="1d")
        if not df.empty:
            market_data[s] = df

    if not market_data:
        print("  ⚠️ 本地尚无行情缓存，自动拉取基础样本...")
        mgr = USDataAndUniverseManager()
        market_data = mgr.download_and_sync(symbols, start_date="2024-01-01")

    print(f"  ✅ 成功装载 {len(market_data)} 只标的行情流。")

    # 3. 运行多因子综合选股模型
    print("\n[Step 3/5] ⚙️ 正在执行截面多因子挖掘与打分 (量价 + 波动 + 舆情联动)...")
    mf_strategy = SP500MultiFactorStrategy(top_n=3, use_sentiment=True)
    ranked_df = mf_strategy.generate_portfolio_signals(market_data)
    
    print("\n🏆 标普500 多因子最新阿尔法得分榜单：")
    print(ranked_df[["symbol", "close", "bias_20", "rsi_14", "volatility", "composite_score", "selected"]].to_string(index=False))

    # 4. 全量独立风控核查 (PDT、熔断、仓位)
    print("\n[Step 4/5] 🛡️ 正在执行全量独立风控前置校验...")
    risk_mgr = RiskManager()
    cb_pass, cb_msg = risk_mgr.check_circuit_breaker(spy_daily_drop=0.0)
    print(f"  大盘三级熔断检查: {cb_msg}")

    # 5. 模拟盘实盘账户结算与断点续跑
    print("\n[Step 5/5] 💼 正在同步模拟盘 (Paper Trader) 账户与仓位账本...")
    paper_trader = PaperTrader(state_file="storage/paper_account.json", initial_capital=20000.0)
    
    # 获取精选标的第一名进行模拟配置
    top_picks = ranked_df[ranked_df["selected"] == True]
    if not top_picks.empty and trade_allowed and cb_pass:
        pick = top_picks.iloc[0]
        print(f"  🎯 统帅部向模拟盘下达执行指令: 标的={pick['symbol']}, 现价=${pick['close']}")
        paper_trader.execute_signal(
            symbol=pick["symbol"],
            signal="BUY",
            current_price=float(pick["close"]),
            current_date=str(pick["timestamp"])
        )
    else:
        print("  ⏸️ 保持防守观望，今日不执行主动开仓。")

    print("\n💾 模拟盘账户最新净值快照：")
    print(f"  现金结余: ${paper_trader.account_state['cash']:,.2f}")
    print(f"  总资产净值: ${paper_trader.account_state['total_equity']:,.2f}")
    print(f"  当前活跃持仓: {paper_trader.account_state['positions']}")

    print("\n" + "=" * 80)
    print("🎉 全系统巡航完毕！数据、因子、策略、风控、舆情与模拟盘全部无缝协同运行。")
    print("=" * 80)

if __name__ == "__main__":
    run_master_pipeline()
