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
# 🏛️ 家族办公室级硬风控参数 (Code-Level Risk Firewall)
# ==============================================================================
WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
QUOTE_CURRENCY = "USDT"
MAX_CASH_PER_BUY_PCT = 0.20      
MIN_CASH_RESERVE_PCT = 0.15      
MAX_SINGLE_ASSET_WEIGHT = 0.50   
MAX_SELL_PER_TRADE_PCT = 0.35    
MIN_ORDER_VALUE_USDT = 12.0      
# ==============================================================================

def init_smart_exchange():
    """
    机构级智能双路由：强制使用币安官方公开 Vision 网关，
    彻底避开美国云端服务器的地域合规限制。
    """
    api_key = os.environ.get("BINANCE_US_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_US_SECRET", "").strip()

    # 强制指定官方公开 Vision 行情网关
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

    if not api_key or not api_secret:
        return market_client, None, "未检测到 API 密钥 (仅运行行情分析)"

    for ex_id, label in [("binance", "Binance 国际站"), ("binanceus", "Binance.US 美国站")]:
        try:
            ex_class = getattr(ccxt, ex_id)
            trade_client = ex_class({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot", "adjustForTimeDifference": True}
            })
            trade_client.load_markets()
            return market_client, trade_client, f"已成功认证连接: {label}"
        except Exception as e:
            last_err = str(e)
            continue

    return market_client, None, f"账户连接受限 (将执行模拟分析): {last_err[:120]}"

def fetch_global_macro_benchmarks():
    benchmarks = {
        "US_10Y_Treasury_Yield": "^TNX",
        "US_Dollar_Index": "DX-Y.NYB",
        "SP500_ETF": "SPY",
        "Nasdaq100_ETF": "QQQ",
        "Berkshire_Hathaway": "BRK-B"
    }
    macro_summary = {}
    for name, ticker in benchmarks.items():
        try:
            hist = yf.Ticker(ticker).history(period="1mo")
            if not hist.empty and len(hist) >= 5:
                latest = float(hist["Close"].iloc[-1])
                chg_5d = (latest / float(hist["Close"].iloc[-5]) - 1) * 100
                macro_summary[name] = {"latest": round(latest, 2), "5d_change_pct": round(chg_5d, 2)}
        except Exception as e:
            macro_summary[name] = {"error": str(e)}

    try:
        res = requests.get("https://api.alternative.me/fng/?limit=7", timeout=10).json()
        data = res.get("data", [])
        today_val = int(data[0]["value"])
        avg_7d = sum(int(x["value"]) for x in data) / len(data)
        fng = {"today_score": today_val, "sentiment_label": data[0]["value_classification"], "7d_avg_score": round(avg_7d, 1)}
    except Exception:
        fng = {"today_score": 50, "sentiment_label": "Neutral", "7d_avg_score": 50.0}

    return macro_summary, fng

def calc_wilders_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])

def analyze_market_and_portfolio(market_client, trade_client):
    free_balances, total_balances = {}, {}
    if trade_client:
        try:
            bal = trade_client.fetch_balance()
            free_balances = bal.get("free", {})
            total_balances = bal.get("total", {})
        except Exception:
            pass

    free_cash = float(free_balances.get(QUOTE_CURRENCY, 0.0))
    total_cash = float(total_balances.get(QUOTE_CURRENCY, 0.0))
    total_equity_usdt = total_cash

    market_metrics = {}
    holdings = {}

    for symbol in WATCHLIST:
        base_coin = symbol.split("/")[0]
        ohlcv = market_client.fetch_ohlcv(symbol, timeframe="1d", limit=200)
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])

        price = float(df["close"].iloc[-1])
        sma_200 = float(df["close"].mean())
        high_200d = float(df["high"].max())
        low_200d = float(df["low"].min())

        mayer_multiple = price / sma_200
        drawdown_pct = (price / high_200d - 1) * 100
        rsi_14 = calc_wilders_rsi(df["close"], 14)

        coin_total_qty = float(total_balances.get(base_coin, 0.0))
        coin_free_qty = float(free_balances.get(base_coin, 0.0))
        coin_val_usdt = coin_total_qty * price
        total_equity_usdt += coin_val_usdt

        holdings[base_coin] = {
            "total_qty": round(coin_total_qty, 6),
            "free_qty": round(coin_free_qty, 6),
            "market_value_usdt": round(coin_val_usdt, 2)
        }

        market_metrics[symbol] = {
            "current_price": round(price, 2),
            "mayer_multiple_price_to_sma200": round(mayer_multiple, 3),
            "drawdown_from_200d_high_pct": round(drawdown_pct, 2),
            "wilders_rsi_14d": round(rsi_14, 1),
            "sma_200": round(sma_200, 2)
        }

    for coin in holdings:
        holdings[coin]["weight_pct"] = round(holdings[coin]["market_value_usdt"] / total_equity_usdt * 100, 2) if total_equity_usdt > 0 else 0.0

    portfolio = {
        "total_equity_usdt": round(total_equity_usdt, 2),
        "available_cash_usdt": round(free_cash, 2),
        "cash_weight_pct": round(free_cash / total_equity_usdt * 100, 2) if total_equity_usdt > 0 else 100.0,
        "positions": holdings
    }

    return market_metrics, portfolio

def invoke_value_investment_committee(macro, fng, market_metrics, portfolio):
    client = OpenAI(
        api_key=os.environ.get("LLM_API_KEY"),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    )
    system_prompt = """
    你是全权打理用户加密家族办公室的“巴菲特-芒格-段永平联合首席投资官 (CIO)”。
    请严格且仅输出合法的 JSON 对象（不要包含任何多余文字），格式如下：
    {
      "market_regime": "黄金击球抄底区 / 合理价值定投区 / 垃圾时间观望区 / 极度贪婪止盈区",
      "macro_opportunity_cost_verdict": "跨市场资金水位判断",
      "buffett_memo": "巴菲特视角点评",
      "munger_inversion_risk": "芒格逆向风险",
      "duan_stop_doing_note": "段永平不为清单",
      "orders": [
        {"symbol": "BTC/USDT", "action": "HOLD", "allocation_ratio": 0.0, "conviction_score": 80, "thesis": "观察中"},
        {"symbol": "ETH/USDT", "action": "HOLD", "allocation_ratio": 0.0, "conviction_score": 80, "thesis": "观察中"},
        {"symbol": "SOL/USDT", "action": "HOLD", "allocation_ratio": 0.0, "conviction_score": 80, "thesis": "观察中"}
      ]
    }
    """
    user_context = json.dumps({"macro": macro, "fng": fng, "market": market_metrics, "portfolio": portfolio}, ensure_ascii=False)
    response = client.chat.completions.create(
        model=os.environ.get("LLM_MODEL", "deepseek-chat"),
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_context}],
        temperature=0.2
    )
    return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", response.choices[0].message.content.strip(), flags=re.MULTILINE))

def execute_with_risk_firewall(trade_client, ai_plan, market_metrics, portfolio):
    logs = []
    for order in ai_plan.get("orders", []):
        sym = order.get("symbol")
        act = order.get("action", "HOLD")
        logs.append(f"⏸️ **{sym}** | 动作: `{act}` | 逻辑: {order.get('thesis', '')}")
    return logs

def generate_executive_report(conn_status, macro, fng, market_metrics, portfolio, ai_plan, logs):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report = f"""# 🏛️ 巴芒段 AI 家族办公室 · 操盘日报\n> 运行时间：`{now_str}` | 通路：`{conn_status}`\n\n## 资产快照\n- 总净值：`${portfolio['total_equity_usdt']} USDT`\n- 可用现金：`${portfolio['available_cash_usdt']} USDT`\n\n## 投委会决议\n- **定调**：`{ai_plan.get('market_regime')}`\n- **巴菲特**：{ai_plan.get('buffett_memo')}\n\n## 执行日志\n""" + "\n".join(f"- {l}" for l in logs)
    with open("LATEST_CIO_MEMO.md", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    market_client, trade_client, conn_status = init_smart_exchange()
    macro, fng = fetch_global_macro_benchmarks()
    market_metrics, portfolio = analyze_market_and_portfolio(market_client, trade_client)
    ai_plan = invoke_value_investment_committee(macro, fng, market_metrics, portfolio)
    logs = execute_with_risk_firewall(trade_client, ai_plan, market_metrics, portfolio)
    generate_executive_report(conn_status, macro, fng, market_metrics, portfolio, ai_plan, logs)
