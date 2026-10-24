import os
import re
import json
import ccxt
import numpy as np
import pandas as pd
from datetime import datetime, timezone

# ==============================================================================
# ⚡ 纯量化交易策略参数
# ==============================================================================
WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
QUOTE_CURRENCY = "USDT"
RSI_OVERSOLD = 32.0        # RSI 超卖买入阈值
RSI_OVERBOUGHT = 68.0      # RSI 超买卖出阈值
TRADE_USDT_AMOUNT = 20.0   # 每次量化下单金额 (USDT)
MIN_ORDER_VALUE = 12.0     # 最小下单限制
# ==============================================================================

def init_quant_exchange():
    """初始化币安现货实盘量化客户端，并强制使用官方 Vision 免限流公开网关"""
    api_key = os.environ.get("BINANCE_US_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_US_SECRET", "").strip()
    
    # 强制指定免地域限制的公开现货行情网关
    market_client = ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
        "urls": {
            "api": {
                "public": "https://data-api.binance.vision/api/v3",
                "private": "https://data-api.binance.vision/api/v3",
                "v1": "https://data-api.binance.vision/api/v1",
                "v3": "https://data-api.binance.vision/api/v3",
            }
        }
    })

    trade_client = None
    conn_status = "免限流行情源就绪 (未配置交易密钥)"

    if api_key and api_secret:
        for ex_id, label in [("binance", "Binance 国际站"), ("binanceus", "Binance.US 美国站")]:
            try:
                ex_class = getattr(ccxt, ex_id)
                client = ex_class({
                    "apiKey": api_key,
                    "secret": api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot", "adjustForTimeDifference": True}
                })
                client.load_markets()
                client.fetch_balance()
                trade_client = client
                conn_status = f"已成功连接 {label} 实盘交易"
                break
            except Exception as e:
                conn_status = f"实盘连接受限: {str(e)[:60]}"
                continue

    return market_client, trade_client, conn_status

def calculate_rsi(series, period=14):
    """计算标准 Wilder's RSI"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])

def run_quant_strategy(market_client, trade_client):
    """核心量化指标计算与信号生成"""
    signals = []
    free_cash = 0.0

    if trade_client:
        try:
            bal = trade_client.fetch_balance()
            free_cash = float(bal.get("free", {}).get(QUOTE_CURRENCY, 0.0))
        except Exception:
            pass

    for symbol in WATCHLIST:
        try:
            ohlcv = market_client.fetch_ohlcv(symbol, timeframe="1h", limit=100)
            df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])
            
            current_price = float(df["close"].iloc[-1])
            rsi_val = calculate_rsi(df["close"], 14)
            sma_20 = float(df["close"].tail(20).mean())
            
            signal = "HOLD"
            reason = f"RSI 正常 ({rsi_val:.1f})"
            
            if rsi_val <= RSI_OVERSOLD:
                signal = "BUY"
                reason = f"RSI 超卖触底 ({rsi_val:.1f} <= {RSI_OVERSOLD})"
            elif rsi_val >= RSI_OVERBOUGHT:
                signal = "SELL"
                reason = f"RSI 超买过热 ({rsi_val:.1f} >= {RSI_OVERBOUGHT})"
                
            signals.append({
                "symbol": symbol,
                "price": current_price,
                "rsi": round(rsi_val, 1),
                "sma_20": round(sma_20, 2),
                "signal": signal,
                "reason": reason
            })
        except Exception as e:
            signals.append({"symbol": symbol, "price": 0.0, "rsi": 0.0, "signal": "ERROR", "reason": str(e)[:60]})
            
    return signals, {"available_cash": round(free_cash, 2)}

def execute_quant_orders(trade_client, signals, portfolio_status):
    """量化自动下单执行器"""
    live_trading = os.environ.get("LIVE_TRADING", "false").lower() == "true"
    execution_logs = []
    avail_cash = portfolio_status.get("available_cash", 0.0)

    for item in signals:
        sym = item["symbol"]
        sig = item["signal"]
        price = item.get("price", 0)
        reason = item.get("reason", "")
        
        if sig == "BUY":
            if avail_cash < TRADE_USDT_AMOUNT:
                execution_logs.append(f"🛡️ **{sym}** | `买入拦截` | 可用现金不足 `{TRADE_USDT_AMOUNT} USDT`")
                continue
                
            raw_qty = TRADE_USDT_AMOUNT / price if price > 0 else 0
            if live_trading and trade_client and raw_qty > 0:
                try:
                    precise_qty = float(trade_client.amount_to_precision(sym, raw_qty))
                    res = trade_client.create_market_buy_order(sym, precise_qty)
                    execution_logs.append(f"✅ **{sym}** | `实盘量化买入` | 数量: `{precise_qty}` | 金额: `~{TRADE_USDT_AMOUNT} USDT` | ID: `{res.get('id')}`")
                except Exception as e:
                    execution_logs.append(f"❌ **{sym}** | `实盘下单报错` | `{str(e)[:80]}`")
            else:
                execution_logs.append(f"🧪 **{sym}** | `模拟量化买入指令` | 触发原因: {reason}")
                
        elif sig == "SELL":
            if live_trading and trade_client:
                try:
                    base = sym.split("/")[0]
                    bal = trade_client.fetch_balance()
                    coin_free = float(bal.get("free", {}).get(base, 0.0))
                    if coin_free * price >= MIN_ORDER_VALUE:
                        precise_qty = float(trade_client.amount_to_precision(sym, coin_free))
                        res = trade_client.create_market_sell_order(sym, precise_qty)
                        execution_logs.append(f"✅ **{sym}** | `实盘量化止盈` | 卖出数量: `{precise_qty}` | ID: `{res.get('id')}`")
                    else:
                        execution_logs.append(f"⏸️ **{sym}** | `跳过卖出` | 持仓市值低于最小交易额")
                except Exception as e:
                    execution_logs.append(f"❌ **{sym}** | `卖出报错` | `{str(e)[:80]}`")
            else:
                execution_logs.append(f"🧪 **{sym}** | `模拟量化止盈` | 触发原因: {reason}")
        else:
            execution_logs.append(f"⏸️ **{sym}** | `观望 (HOLD)` | {reason}")
            
    return execution_logs

def generate_quant_report(conn_status, signals, portfolio_status, logs):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    signal_rows = []
    for s in signals:
        signal_rows.append(f"| **{s['symbol']}** | `${s.get('price', 0)}` | `{s.get('rsi', 'N/A')}` | `{s['signal']}` | {s['reason']} |")
    signal_table = "\n".join(signal_rows)

    report = f"""# ⚡ 币安全自动量化交易引擎 · 实时交割日报
> **执行时间**：`{now_str}` ｜ **通道状态**：`{conn_status}` ｜ **策略模式**：`RSI 动量量化策略`

## 一、 账户资产水位
* **可用 USDT 现金**：`${portfolio_status.get('available_cash', 0.0)} USDT`
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
    market_client, trade_client, conn_status = init_quant_exchange()
    signals, portfolio_status = run_quant_strategy(market_client, trade_client)
    logs = execute_quant_orders(trade_client, signals, portfolio_status)
    generate_quant_report(conn_status, signals, portfolio_status, logs)
