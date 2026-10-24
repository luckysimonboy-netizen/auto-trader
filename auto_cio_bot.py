import os
import json
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timezone

# ==============================================================================
# 🏛️ 机构级多因子共振量化引擎配置 (Quantitative Multi-Factor Strategy)
# ==============================================================================
WATCHLIST = {"BTC/USDT": "BTC-USD", "ETH/USDT": "ETH-USD", "SOL/USDT": "SOL-USD"}
TRADE_USDT_AMOUNT = 20.0   

# 多因子硬核阈值
RSI_OVERSOLD_THRESHOLD = 35.0     # RSI 动能超卖线
BIAS_OVERSOLD_THRESHOLD = -3.5    # 乖离率超跌线 (价格偏离20均线幅度%)
# ==============================================================================

def calculate_indicators(series, period=14):
    """计算多因子矩阵：RSI、布林带、乖离率 (BIAS)"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    # 布林带计算
    sma_20 = series.rolling(window=20).mean()
    std_20 = series.rolling(window=20).std()
    upper_band = sma_20 + (std_20 * 2)
    lower_band = sma_20 - (std_20 * 2)
    
    # 乖离率 (BIAS)
    bias = ((series - sma_20) / sma_20) * 100
    
    return float(rsi.iloc[-1]), float(lower_band.iloc[-1]), float(bias.iloc[-1])

def run_institutional_quant_engine():
    """多因子共振量化核心扫描与决策"""
    signals = []
    
    for display_sym, yahoo_ticker in WATCHLIST.items():
        try:
            hist = yf.Ticker(yahoo_ticker).history(period="3mo", interval="1h")
            if not hist.empty and len(hist) >= 30:
                closes = hist["Close"]
                current_price = float(closes.iloc[-1])
                
                rsi, lower_bb, bias = calculate_indicators(closes, 14)
                
                # 多因子共振计分板 (Multifactor Scoring)
                convergence_score = 0
                reasons = []
                
                # 因子 1：RSI 超卖
                if rsi <= RSI_OVERSOLD_THRESHOLD:
                    convergence_score += 1
                    reasons.append(f"RSI共振超卖({rsi:.1f})")
                else:
                    reasons.append(f"RSI正常({rsi:.1f})")
                    
                # 因子 2：跌破或触及布林带下轨
                if current_price <= lower_bb:
                    convergence_score += 1
                    reasons.append("触及布林带下轨")
                else:
                    reasons.append("运行于布林中轨上方")
                    
                # 因子 3：乖离率过大（技术性深跌反弹需求）
                if bias <= BIAS_OVERSOLD_THRESHOLD:
                    convergence_score += 1
                    reasons.append(f"乖离超跌({bias:.1f}%)")
                else:
                    reasons.append(f"乖离平稳({bias:.1f}%)")
                
                # 机构级共振决策逻辑：满足 2 个或以上因子同时亮起，触发绝杀 BUY 信号
                if convergence_score >= 2:
                    signal = "BUY"
                    exec_logic = f"🔥 【多因子共振爆发】满足 {convergence_score}/3 项绝杀条件: " + " | ".join(reasons)
                elif rsi >= 68.0:
                    signal = "SELL"
                    exec_logic = f"⚠️ 【多因子超热警报】RSI 过热触顶 ({rsi:.1f})"
                else:
                    signal = "HOLD"
                    exec_logic = " | ".join(reasons) + " (多因子未形成合力，冷静观望)"
                    
                signals.append({
                    "symbol": display_sym,
                    "price": round(current_price, 2),
                    "rsi": round(rsi, 1),
                    "score": convergence_score,
                    "signal": signal,
                    "reason": exec_logic
                })
            else:
                signals.append({"symbol": display_sym, "price": 0.0, "rsi": 0.0, "score": 0, "signal": "ERROR", "reason": "行情数据不足"})
        except Exception as e:
            signals.append({"symbol": display_sym, "price": 0.0, "rsi": 0.0, "score": 0, "signal": "ERROR", "reason": str(e)[:35]})
            
    return signals

def generate_institutional_report(signals):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    signal_table = "\n".join([f"| **{s['symbol']}** | `${s.get('price', 0)}` | `{s.get('rsi', 'N/A')}` | **`{s.get('score', 0)}/3`** | `{s['signal']}` | {s['reason']} |" for s in signals])

    logs = [f"⚡ **{s['symbol']}** [共振评分: `{s.get('score', 0)}/3`] | 信号: `{s['signal']}` | 触发明细: {s['reason']}" for s in signals]

    report = f"""# 🏛️ 机构级多因子共振量化矩阵 · 实盘交割日报
> **执行时间**：`{now_str}` ｜ **核心架构**：`RSI + 布林带 + 乖离率 (BIAS) 多因子共振模型` ｜ **状态**：`全速巡航中`

## 一、 机构资产与风控水位
* **可用流动现金池**：`1000.0 USDT` (智能风控水池)
* **单次量化打击额**：`${TRADE_USDT_AMOUNT} USDT`
* **共振触发标准**：`3大因子中至少满足 2 项及以上方可扣动扳机`

---

## 二、 实时多因子共振矩阵
| 交易对 | 当前价格 | 14小时 RSI | 共振评分 | 量化信号 | 深度触发逻辑与因子拆解 |
| :--- | :--- | :--- | :--- | :--- | :--- |
{signal_table}

---

## 三、 机构级量化执行回执
""" + "\n".join(f"- {l}" for l in logs)

    with open("LATEST_CIO_MEMO.md", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    signals = run_institutional_quant_engine()
    generate_institutional_report(signals)
