import os
import re
import json
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from openai import OpenAI
from datetime import datetime, timezone

# ==============================================================================
# 🏛️ 极简稳健版风控参数
# ==============================================================================
WATCHLIST = ["BTC-USD", "ETH-USD", "SOL-USD"]  # 直接使用 Yahoo 现货行情源，全球 100% 畅通
QUOTE_CURRENCY = "USDT"
MIN_CASH_RESERVE_PCT = 0.15      
# ==============================================================================

def fetch_market_and_macro():
    """使用 Yahoo Finance 稳定获取加密货币现货与宏观指数"""
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
                    "mayer_multiple_price_to_sma200": round(mayer, 3),
                    "drawdown_from_200d_high_pct": round(drawdown, 2),
                    "sma_200": round(sma_200, 2)
                }
        except Exception as e:
            print(f"Error fetching {sym}: {e}")

    # 获取恐慌贪婪指数
    try:
        fng_res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
        fng_data = fng_res.get("data", [{}])[0]
        fng = {
            "today_score": int(fng_data.get("value", 50)),
            "sentiment_label": fng_data.get("value_classification", "Neutral")
        }
    except Exception:
        fng = {"today_score": 50, "sentiment_label": "Neutral"}

    return market_metrics, fng

def invoke_value_investment_committee(fng, market_metrics):
    client = OpenAI(
        api_key=os.environ.get("LLM_API_KEY"),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    )
    system_prompt = """
    你是巴菲特-芒格-段永平联合首席投资官 (CIO)。请仅输出合法 JSON：
    {
      "market_regime": "合理价值定投区 / 黄金击球抄底区",
      "buffett_memo": "巴菲特视角点评",
      "munger_inversion_risk": "芒格逆向风险",
      "orders": [
        {"symbol": "BTC/USDT", "action": "HOLD", "thesis": "观察中"},
        {"symbol": "ETH/USDT", "action": "HOLD", "thesis": "观察中"},
        {"symbol": "SOL/USDT", "action": "HOLD", "thesis": "观察中"}
      ]
    }
    """
    user_context = json.dumps({"fng": fng, "market": market_metrics}, ensure_ascii=False)
    response = client.chat.completions.create(
        model=os.environ.get("LLM_MODEL", "deepseek-chat"),
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_context}],
        temperature=0.2
    )
    return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", response.choices[0].message.content.strip(), flags=re.MULTILINE))

def generate_executive_report(fng, market_metrics, ai_plan):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    market_rows = []
    for sym, m in market_metrics.items():
        market_rows.append(f"| **{sym}** | `${m['current_price']}` | `{m['mayer_multiple_price_to_sma200']}x` | `{m['drawdown_from_200d_high_pct']}%` |")
    market_table = "\n".join(market_rows)

    report = f"""# 🏛️ 巴芒段 AI 家族办公室 · 操盘日报
> **执行时间**：`{now_str}` ｜ **状态**：`运行正常 (Yahoo 稳定源)`

## 一、 市场情绪与估值矩阵
* **加密恐慌贪婪指数**：`{fng['today_score']}` ({fng['sentiment_label']})

| 交易对 | 最新价格 | 梅耶倍数 (现价/200日线) | 距高点回撤 |
| :--- | :--- | :--- | :--- |
{market_table}

---

## 二、 投委会共识决议
* 🎯 **市场定调**：**`{ai_plan.get('market_regime')}`**
* 🎩 **巴菲特视角**：{ai_plan.get('buffett_memo')}
* 👓 **芒格逆向警钟**：{ai_plan.get('munger_inversion_risk')}
"""
    with open("LATEST_CIO_MEMO.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("Report generated successfully.")

if __name__ == "__main__":
    market_metrics, fng = fetch_market_and_macro()
    ai_plan = invoke_value_investment_committee(fng, market_metrics)
    generate_executive_report(fng, market_metrics, ai_plan)
