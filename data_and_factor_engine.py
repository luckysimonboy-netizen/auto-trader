import os
import json
import concurrent.futures
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timezone

# ==============================================================================
# 🏛️ 工业级全景量化智能体 · 核心因子工厂与数据管道
# ==============================================================================
UNIVERSE_POOL = [
    "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", 
    "AMD", "COIN", "NFLX", "PLTR", "SPY", "QQQ", "VOOG",
    "BTC-USD", "ETH-USD", "SOL-USD"
]

TRADE_USDT_AMOUNT = 20.0   
# ==============================================================================

class QuantFactorFactory:
    """高性能量化特征与因子挖掘工厂"""
    
    @staticmethod
    def compute_technical_factors(series: pd.Series) -> dict:
        """多维技术因子计算：动量、波动率、乖离率、成交量异动"""
        if len(series) < 30:
            return {}
            
        # 1. 14周期 Wilder's RSI
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        # 2. 布林带 (Bollinger Bands)
        sma_20 = series.rolling(window=20).mean()
        std_20 = series.rolling(window=20).std()
        upper_band = sma_20 + (std_20 * 2)
        lower_band = sma_20 - (std_20 * 2)
        
        # 3. 乖离率 (BIAS)
        bias = ((series - sma_20) / sma_20) * 100
        
        # 4. 波动率 (Volatility)
        volatility = series.pct_change().rolling(window=20).std() * np.sqrt(252) * 100

        return {
            "close": float(series.iloc[-1]),
            "rsi": float(rsi.iloc[-1]),
            "sma_20": float(sma_20.iloc[-1]),
            "upper_band": float(upper_band.iloc[-1]),
            "lower_band": float(lower_band.iloc[-1]),
            "bias": float(bias.iloc[-1]),
            "volatility": float(volatility.iloc[-1]) if not np.isnan(volatility.iloc[-1]) else 0.0
        }

def fetch_and_process_ticker(ticker: str) -> dict:
    """单标的高性能多线程并行清洗与评分"""
    try:
        hist = yf.Ticker(ticker).history(period="3mo", interval="1h")
        if hist.empty or len(hist) < 30:
            return None
            
        closes = hist["Close"]
        factors = QuantFactorFactory.compute_technical_factors(closes)
        if not factors:
            return None
            
        current_price = factors["close"]
        rsi = factors["rsi"]
        lower_bb = factors["lower_band"]
        bias = factors["bias"]
        volatility = factors["volatility"]
        
        # 机构级多因子共振打分模型 (Multi-Factor Scoring Matrix)
        score = 0
        reasons = []
        
        if rsi <= 35.0:
            score += 1
            reasons.append(f"RSI深度超卖({rsi:.1f})")
        else:
            reasons.append(f"RSI中性({rsi:.1f})")
            
        if current_price <= lower_bb:
            score += 1
            reasons.append("触及布林下轨")
        else:
            reasons.append("布林带运行平稳")
            
        if bias <= -3.5:
            score += 1
            reasons.append(f"乖离超跌({bias:.1f}%)")
        else:
            reasons.append(f"乖离正常({bias:.1f}%)")
            
        # 策略评级
        if score >= 2:
            signal = "🔥 绝杀多因子 BUY"
        elif rsi >= 68.0:
            signal = "⚠️ 超热 SELL"
        else:
            signal = "⏸️ 观望 HOLD"
            
        return {
            "ticker": ticker.replace("-USD", "/USDT"),
            "price": round(current_price, 2),
            "rsi": round(rsi, 1),
            "bias": round(bias, 2),
            "volatility": round(volatility, 2),
            "score": score,
            "signal": signal,
            "reason": " | ".join(reasons)
        }
    except Exception:
        return None

def run_distributed_pipeline():
    """分布式多线程全市场并行扫描主控"""
    print(f"🚀 [Quant Agent] 正在启动全景多线程數據管線，監控池容量: {len(UNIVERSE_POOL)}...")
    results = []
    
    # 采用高并发线程池，瞬间吞吐全市场数据
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_ticker = {executor.submit(fetch_and_process_ticker, t): t for t in UNIVERSE_POOL}
        for future in concurrent.futures.as_completed(future_to_ticker):
            res = future.result()
            if res:
                results.append(res)
                
    # 按多因子共振得分降序排列
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def generate_enterprise_report(results):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    table_rows = []
    for r in results:
        table_rows.append(f"| **{r['ticker']}** | `${r['price']}` | `{r['rsi']}` | `{r['bias']}%` | `{r['volatility']}%` | **`{r['score']}/3`** | `{r['signal']}` | {r['reason']} |")
    
    signal_table = "\n".join(table_rows)

    report = f"""# 🏛️ 工业级 AI 量化智能体帝国 · 全景多因子情报日报
> **执行时间**：`{now_str}` ｜ **架构内核**：`分布式多线程并发管道 + 高维因子工厂` ｜ **状态**：`全速吞吐中`

## 一、 系统架构与风控水位
* **高并发并行线程**：`8 线程异步并发`
* **监控资产广度**：`{len(results)} 只全球顶级美股与加密资产`
* **单次猎杀建仓额**：`${TRADE_USDT_AMOUNT} USDT`

---

## 二、 全景多因子猎杀与阿尔法排行榜
| 标的资产 | 当前价格 | 14h RSI | 乖离率(BIAS) | 年化波动率 | 共振评分 | 智能体决策 | 因子拆解与深度透视 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{signal_table}

---

## 三、 量化智能体调度回执
* 模块一（数据管道与因子工程）已成功通过分布式多线程吞吐全市场数据。
* 准备加载**模块二：机器学习/强化学习信号预测与賽博投委會集成模組**。
"""

    with open("LATEST_CIO_MEMO.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("✅ 工业级因子情报日报生成完毕。")

if __name__ == "__main__":
    market_data = run_distributed_pipeline()
    generate_enterprise_report(market_data)
