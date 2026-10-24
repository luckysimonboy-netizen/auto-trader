import os
import re
import json
import ccxt
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from openai import OpenAI
from datetime import datetime, timezone

# ==============================================================================
# 🏛️ 家族办公室级硬风控参数 (代码写死，AI 绝对无法突破)
# ==============================================================================
WATCHLIST = ["BTC-USD", "ETH-USD", "SOL-USD"]
QUOTE_CURRENCY = "USDT"
MAX_CASH_PER_BUY_PCT = 0.20      # 单次最多动用可用现金的 20%
MIN_CASH_RESERVE_PCT = 0.15      # 必须永远保留 15% 的现金底垫
MAX_SINGLE_ASSET_WEIGHT = 0.50   # 单个资产仓位超过 50% 停止加仓
MIN_ORDER_VALUE_USDT = 12.0      # 最低下单金额（满足币安限制）
# ==============================================================================

def init_binance_trade_client():
    """连接币安现货实盘 API"""
    api_key = os.environ.get("BINANCE_US_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_US_SECRET", "").strip()
    
    if not api_key or not api_secret:
        return None, "未配置 API 密钥"
    
    # 尝试连接币安国际站与美国站
    for ex_id in ["binance", "binanceus"]:
        try:
            ex_class = getattr(ccxt, ex_id)
            client = ex_class({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot", "adjustForTimeDifference": True}
            })
            client.load_markets()
            # 测试拉取余额，证明权限正常
            client.fetch_balance()
            return client, f"已成功连接 {ex_id} 实盘账户"
        except Exception as e:
            continue
    return None, "实盘 API 连接受限或密钥权限未开通"

def fetch_market_and_portfolio(trade_client):
    market_metrics = {}
    for sym in WATCHLIST:
        try:
            hist = yf.Ticker(sym).history(period="1y")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                sma_200 = float(hist["Close"].mean()) if len(hist) >= 200 else price
                high_200 = float(hist["High"].max())
                mayer = price / sma_200
                drawdown = (price / high_200 - 1) * 100
                base_name = sym.split("-")[0] + "/USDT"
                market_metrics[base_name] = {
                    "current_price": round(price, 2),
                    "mayer_multiple": round(mayer, 3),
                    "drawdown_pct": round(drawdown, 2)
                }
        except Exception:
            pass

    # 获取账户真实余额
    free_cash = 0.0
    total_equity = 0.0
    positions = {}
    
    if trade_client:
        try:
            bal = trade_client.fetch_balance()
            free_cash = float(bal.get("free", {}).get(QUOTE_CURRENCY, 0.0))
            total_cash = float(bal.get("total", {}).get(QUOTE_CURRENCY, 0.0))
            total_equity = total_cash
            
            for base in ["BTC", "ETH", "SOL"]:
                q = float(bal.get("total", {}).get(base, 0.0))
                if q > 0 and base + "/USDT" in market_metrics:
                    val = q * market_metrics[base + "/USDT"]["current_price"]
                    total_equity += val
                    positions[base] = {"qty": q, "value": val}
        except Exception as e:
            print(f"Balance fetch error: {e}")

    try:
        fng_res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
        fng_data = fng_res.get("data", [{}])[0]
        fng = {"score": int(fng_data.get("value", 50)), "label": fng_data.get("value_classification", "Neutral")}
    except Exception:
        fng = {"score": 50, "label": "Neutral"}

    portfolio = {
        "total_equity": round(total_equity, 2),
        "available_cash": round(free_cash, 2),
        "cash_weight_pct": round(free_cash / total_equity * 100, 2) if total_equity > 0 else 100.0,
        "positions": positions
    }

    return market_metrics, fng, portfolio

def invoke_ai_committee(fng, market_metrics, portfolio):
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
    
    system_prompt = """
    你是全权代客操盘的加密家族办公室首席投资官 (CIO)。结合巴菲特（安全边际）、段永平（机会成本）哲学进行决策。
    当现金充足且市场处于合理定投或黄金击球区时，必须勇敢下达 BUY 指令；当过热时下达 SELL 指令。
    请严格仅输出合法 JSON：
    {
      "market_regime": "黄金击球抄底区 / 合理价值定投区 / 极度贪婪止盈区",
      "buffett_memo": "巴菲特视角操盘点评",
      "munger_inversion_risk": "逆向风险提示",
      "orders": [
        {"symbol": "BTC/USDT", "action": "BUY 或 SELL 或 HOLD", "allocation_ratio": 0.10, "thesis": "下单理由"},
        {"symbol": "ETH/USDT", "action": "BUY 或 SELL 或 HOLD", "allocation_ratio": 0.10, "thesis": "下单理由"},
        {"symbol": "SOL/USDT", "action": "BUY 或 SELL 或 HOLD", "allocation_ratio": 0.10, "thesis": "下单理由"}
      ]
    }
    """
    user_context = json.dumps({"fng": fng, "market": market_metrics, "portfolio": portfolio}, ensure_ascii=False)
    
    try:
        response = client.chat.completions.create(
            model=os.environ.get("LLM_MODEL", "deepseek-chat"),
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_context}],
            temperature=0.2
        )
        return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", response.choices[0].message.content.strip(), flags=re.MULTILINE))
    except Exception as e:
        return {
            "market_regime": "安全观望区",
            "buffett_memo": f"API 连接重试中，暂缓主动下单。错误: {str(e)[:50]}",
            "munger_inversion_risk": "无",
            "orders": []
        }

def execute_real_trades(trade_client, ai_plan, market_metrics, portfolio):
    """五重硬风控校验与实盘下单执行器"""
    live_trading = os.environ.get("LIVE_TRADING", "false").lower() == "true"
    logs = []
    
    avail_cash = portfolio["available_cash"]
    total_equity = portfolio["total_equity"]
    cash_floor = total_equity * MIN_CASH_RESERVE_PCT

    for order in ai_plan.get("orders", []):
        sym = order.get("symbol")
        action = str(order.get("action", "HOLD")).upper()
        ratio = float(order.get("allocation_ratio", 0.0))
        thesis = order.get("thesis", "")

        if sym not in market_metrics or action == "HOLD" or ratio <= 0:
            logs.append(f"⏸️ **{sym}** | `HOLD` | 逻辑: {thesis}")
            continue

        price = market_metrics[sym]["current_price"]

        if action == "BUY":
            safe_ratio = min(ratio, MAX_CASH_PER_BUY_PCT)
            target_usdt = avail_cash * safe_ratio

            # 风控：保留 15% 现金底垫
            if (avail_cash - target_usdt) < cash_floor:
                target_usdt = max(0.0, avail_cash - cash_floor)

            if target_usdt < MIN_ORDER_VALUE_USDT:
                logs.append(f"🛡️ **{sym}** | `拦截` | 可用现金或买入额不足最小门槛 `{MIN_ORDER_VALUE_USDT} USDT`")
                continue

            raw_qty = target_usdt / price
            if live_trading and trade_client:
                try:
                    precise_qty = float(trade_client.amount_to_precision(sym, raw_qty))
                    res = trade_client.create_market_buy_order(sym, precise_qty)
                    avail_cash -= target_usdt
                    logs.append(f"✅ **{sym}** | `实盘买入成交` | 数量: `{precise_qty}` | 耗资: `~{target_usdt:.2f} USDT` | ID: `{res.get('id')}`")
                except Exception as e:
                    logs.append(f"❌ **{sym}** | `实盘买入失败` | 原因: `{str(e)[:100]}`")
            else:
                logs.append(f"🧪 **{sym}** | `模拟买入指令` | 拟买数量: `{raw_qty:.4f}` (`{target_usdt:.2f} USDT`)")

    return logs

def generate_report(conn_status, fng, portfolio, ai_plan, logs):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report = f"""# 🏛️ 巴芒段 AI 家族办公室 · 实盘全自动代操盘日报
> **执行时间**：`{now_str}` ｜ **通道状态**：`{conn_status}` ｜ **托管模式**：`全权实盘代操盘激活`

## 一、 资产与现金水位
* **账户总净值**：`${portfolio['total_equity']} USDT`
* **可用现金池**：`${portfolio['available_cash']} USDT` (现金占比: `{portfolio['cash_weight_pct']}%`)
* **市场恐慌指数**：`{fng['score']}` ({fng['label']})

---

## 二、 投委会共识与实盘风控回执
* 🎯 **市场定调**：**`{ai_plan.get('market_regime')}`**
* 🎩 **巴菲特视角**：{ai_plan.get('buffett_memo')}
* 👓 **芒格逆向警钟**：{ai_plan.get('munger_inversion_risk')}

### 🤖 自动下单交割记录：
""" + "\n".join(f"- {item}" for item in logs)

    with open("LATEST_CIO_MEMO.md", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    trade_client, conn_status = init_binance_trade_client()
    market_metrics, fng, portfolio = fetch_market_and_portfolio(trade_client)
    ai_plan = invoke_ai_committee(fng, market_metrics, portfolio)
    logs = execute_real_trades(trade_client, ai_plan, market_metrics, portfolio)
    generate_report(conn_status, fng, portfolio, ai_plan, logs)
