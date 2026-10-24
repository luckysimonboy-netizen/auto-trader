"""
🏛️ 美股/加密量化智能体 · 专属移动端可视化面板 (Streamlit App)
"""
import streamlit as st
import pandas as pd
import json
import os

from data.storage_engine import HybridStorageEngine
from sentiment.sentiment_monitor import SentimentMacroMonitor
from strategy.sp500_multifactor_strategy import SP500MultiFactorStrategy

# 1. 页面全局配置 (移动端优先卡片设计)
st.set_page_config(
    page_title="AI Quant 控制台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🏛️ AI Quant 智能体总控中心")
st.caption("美股 & 加密资产实时决策与风控看板")

# 2. 顶部仪表盘：模拟盘资产与风控状态
col1, col2 = st.columns(2)

state_file = "storage/paper_account.json"
paper_state = {"total_equity": 20000.0, "cash": 20000.0, "positions": {}}
if os.path.exists(state_file):
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            paper_state = json.load(f)
    except Exception:
        pass

sent_monitor = SentimentMacroMonitor()
trade_allowed, sent_msg = sent_monitor.get_latest_risk_status()

with col1:
    st.metric(
        label="总资产净值 (Equity)",
        value=f"${paper_state.get('total_equity', 0):,.2f}",
        delta=f"可用现金: ${paper_state.get('cash', 0):,.2f}"
    )

with col2:
    status_label = "🟢 正常交易" if trade_allowed else "🔴 舆情防守"
    st.metric(
        label="风控闸门",
        value=status_label,
        delta="实时联动"
    )

st.divider()

# 3. 实时舆情雷达卡片
st.subheader("📡 特朗普与宏观舆情雷达")
if trade_allowed:
    st.success("🟢 舆情面平稳，各大市场正常开放交易。")
else:
    st.error(f"⚠️ {sent_msg}")

# 4. 多因子智能体选股排行榜
st.subheader("🏆 标普500 多因子狙击榜")
storage = HybridStorageEngine()
symbols = ["AAPL", "NVDA", "TSLA", "MSFT", "SPY"]
market_data = {}
for s in symbols:
    df = storage.load_data(s, interval="1d")
    if not df.empty:
        market_data[s] = df

if market_data:
    strategy = SP500MultiFactorStrategy(top_n=3, use_sentiment=True)
    ranked = strategy.generate_portfolio_signals(market_data)
    if not ranked.empty:
        show_cols = ["symbol", "close", "bias_20", "rsi_14", "composite_score", "selected"]
        st.dataframe(
            ranked[show_cols].rename(columns={
                "symbol": "标的代码",
                "close": "最新价",
                "bias_20": "乖离率(%)",
                "rsi_14": "RSI指标",
                "composite_score": "综合得分",
                "selected": "入选组合"
            }),
            use_container_width=True
        )
else:
    st.info("本地暂无行情缓存，请先在终端运行一次 `python main.py` 加载数据。")

# 5. 模拟盘持仓详情
st.subheader("💼 当前持仓账本")
positions = paper_state.get("positions", {})
if positions:
    pos_list = []
    for sym, details in positions.items():
        pos_list.append({
            "标的": sym,
            "持仓股数": details.get("shares", 0),
            "成本均价": f"${details.get('avg_cost', 0):.2f}"
        })
    st.table(pd.DataFrame(pos_list))
else:
    st.write("暂无持仓，系统处于现金避险状态。")
