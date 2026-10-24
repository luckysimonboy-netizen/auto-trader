import os
import json
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timezone

# ==============================================================================
# 🎯 全市场机构级量化猎杀股票池 (Universe Screening)
# ==============================================================================
UNIVERSE = [
    "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", 
    "AMD", "COIN", "NFLX", "PLTR", "SPY", "QQQ", "VOOG"
]

TRADE_USDT_AMOUNT = 20.0   
RSI_OVERSOLD_THRESHOLD = 35.0     # RSI 超卖线
BIAS_OVERSOLD_THRESHOLD = -3.5    # 乖离率超跌线 (%)
# ==============================================================================

def calculate_indicators(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    sma_20 = series.rolling(window=20).mean()
    std_20 = series.rolling(window=20).std()
    lower_band = sma_20 - (std_20 * 2)
    
    bias = ((series - sma_20) / sma_20) * 100
    
    return float(rsi.iloc[-1]), float(lower_band.iloc[-1]), float(bias.iloc[-1])

def run_universe_screening():
    """全市场并行扫描与多因子猎杀打分"""
    results = []
    
    for ticker in UNIVERSE:
        try:
            hist = yf.Ticker(ticker).history(period="3mo", interval="1h")
            if not hist.empty and len(hist) >= 30:
                closes = hist["Close"]
                current_price = float(closes.iloc[-1])
                
                rsi, lower_bb, bias = calculate_indicators(closes, 14)
                
                score = 0
                reasons = []
                
                if rsi <= RSI_OVERSOLD_THRESHOLD:
                    score += 1
                    reasons.append(f"RSI超卖({rsi:.1f})")
                else:
                    reasons.append(f"RSI正常({rsi:.1f})")
                    
                if current_price <= lower_bb:
                    score += 1
                    reasons.append("触及布林下轨")
                else:
                    reasons.append("布林运行平稳")
                    
                if bias <= BIAS_OVERSOLD_THRESHOLD:
                    score += 1
                    reasons.append(f"乖离超跌({bias:.1f}%)")
                else:
                    reasons.append(f"乖离平稳({bias:.1f}%)")
                
                # 策略评级
                if score >= 2:
                    signal = "🔥 绝杀 BUY"
                elif rsi >= 68.0:
                    signal = "⚠️ 超热 SELL"
                else:
                    signal = "⏸️ 观望 HOLD"
                    
                results.append({
                    "ticker": ticker,
                    "price": round(current_price, 2),
                    "rsi": round(rsi, 1),
                    "bias": round(bias, 2),
                    "score": score,
                    "signal": signal,
                    "reason": " | ".join(reasons)
                })
        except Exception:
            continue
            
    # 按共振得分降序排列，把最危险/最具杀伤力的猎物排在最前
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def generate_universe_report(results):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    table_rows = []
    for r in results:
        table_rows.append(f"| **{r['ticker']}** | `${r['price']}` | `{r['rsi']}` | `{r['bias']}%` | **`{r['score']}/3`** | `{r['signal']}` | {r['reason']} |")
    
    signal_table = "\n".join(table_rows)

    report = f"""# 🎯 全市场多因子量化猎杀矩阵 · 实时情报日报
> **执行时间**：`{now_str}` ｜ **监控池容量**：`{len(results)} 只核心美股与指数` ｜ **策略模式**：`机构级多因子共振猎杀`

## 一、 资本与风控水位
* **全市场扫描状态**：`無死角高速并发巡航`
* **单次猎杀建仓额**：`${TRADE_USDT_AMOUNT} USDT` 

---

## 二、 全市场猎杀排行榜（按共振得分排序）
| 标的 | 当前价格 | 14h RSI | 乖离率(BIAS) | 共振评分 | 猎杀信号 | 核心技术因子拆解 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{signal_table}

---

## 三、 量化指挥部作战回执
* 系统已完成全市场多因子并行扫描，等待高胜率黄金坑瞬间触发自动狙击。
"""

    with open("LATEST_CIO_MEMO.md", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    results = run_universe_screening()
    generate_universe_report(results)
