import os
import json
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timezone

# ==============================================================================
# ⚡ 雅虎财经稳定现货源量化交易策略参数
# ==============================================================================
WATCHLIST = {"BTC/USDT": "BTC-USD", "ETH/USDT": "ETH-USD", "SOL/USDT": "SOL-USD"}
RSI_OVERSOLD = 32.0        
RSI_OVERBOUGHT = 68.0      
TRADE_USDT_AMOUNT = 20.0   
# ==============================================================================

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])

def run_yahoo_quant_strategy():
    """使用 100% 畅通的 Yahoo Finance 现货数据计算 RSI 指标"""
    signals = []
    
    for display_sym, yahoo_ticker in WATCHLIST.items():
        try:
            hist = yf.Ticker(yahoo_ticker).history(period="3mo", interval="1h")
            if not hist.empty and len(hist) >= 20:
                closes = hist["Close"]
                current_price = float(closes.iloc[-1])
                rsi_val = calculate_rsi(closes, 14)
                
                signal = "HOLD"
                reason = f"RSI 正常走势 ({rsi_val:.1f})"
                
                if rsi_val <= RSI_OVERSOLD:
                    signal = "BUY"
                    reason = f"RSI 超卖触底信号 ({rsi_val:.1f})"
                elif rsi_val >= RSI_OVERBOUGHT:
                    signal = "SELL"
                    reason = f"RSI 超买过热信号 ({rsi_val:.1f})"
                    
                signals.append({
                    "symbol": display_sym,
                    "price": round(current_price, 2),
                    "rsi": round(rsi_val, 1),
                    "signal": signal,
                    "reason": reason
                })
            else:
                signals.append({"symbol": display_sym, "price": 0.0, "rsi": 0.0, "signal": "ERROR", "reason": "行情数据不足"})
        except Exception as e:
            signals.append({"symbol": display_sym, "price": 0.0, "rsi": 0.0, "signal": "ERROR", "reason": str(e)[:35]})
            
    return signals

def generate_quant_report(signals):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    signal_table = "\n".join([f"| **{s['symbol']}** | `${s.get('price', 0)}` | `{s.get('rsi', 'N/A')}` | `{s['signal']}` | {s['reason']} |" for s in signals])

    logs = [f"⚡ **{s['symbol']}** | 信号: `{s['signal']}` | 触发逻辑: {s['reason']}" for s in signals]

    report = f"""# ⚡ 现货云端量化引擎 · 实时交割日报
> **执行时间**：`{now_str}` ｜ **通道状态**：`Yahoo 稳定源直连 (100% 畅通)` ｜ **策略模式**：`RSI 动量量化策略`

## 一、 账户资产水位
* **可用流动现金池**：`1000.0 USDT` (虚拟量化测试水位)
* **单次量化下单额**：`${TRADE_USDT_AMOUNT} USDT`

---

## 二、 实时量化指标与信号矩阵
| 交易对 | 当前价格 | 14小时 RSI | 量化信号 | 触发逻辑 |
| :--- | :--- | :--- | :--- | :--- |
{signal_table}

---

## 三、 量化交易执行回执
""" + "\n".join(f"- {l}" for l in logs)

    with open("LATEST_CIO_MEMO.md", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    signals = run_yahoo_quant_strategy()
    generate_quant_report(signals)
