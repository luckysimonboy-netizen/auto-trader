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
# 🏛️ 家族办公室级硬风控参数 (Code-Level Risk Firewall - AI 绝对无权突破)
# ==============================================================================
WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
QUOTE_CURRENCY = "USDT"
MAX_CASH_PER_BUY_PCT = 0.20      # 单次买入最多动用当前可用现金的 20%
MIN_CASH_RESERVE_PCT = 0.15      # 巴菲特安全垫：永远保留总净值 15% 以上的 USDT 现金
MAX_SINGLE_ASSET_WEIGHT = 0.50   # 单一币种占总资产比例超过 50% 时停止继续买入
MAX_SELL_PER_TRADE_PCT = 0.35    # 单次止盈最多卖出该币种可用持仓的 35%
MIN_ORDER_VALUE_USDT = 12.0      # 低于 12 USDT 的碎单自动拦截，满足币安最小交易限额
# ==============================================================================


def init_smart_exchange():
    """
    机构级智能双路由：强制指定免地域限制的官方 Vision 公开行情网关，
    完美绕过 GitHub 云端服务器的 IP 地区合规限制。
    """
    api_key = os.environ.get("BINANCE_US_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_US_SECRET", "").strip()

    # 强制指定全球免限制公开行情网关
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

    # 尝试连接交易客户端
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


    # 自动探测用户的密钥属于 binance.com 还是 binance.us
    for ex_id, label in [("binance", "Binance.com 国际站"), ("binanceus", "Binance.US 美国站")]:
        try:
            ex_class = getattr(ccxt, ex_id)
            trade_client = ex_class({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot", "adjustForTimeDifference": True}
            })
            trade_client.fetch_balance()
            trade_client.load_markets()
            return market_client, trade_client, f"已成功认证连接: {label}"
        except Exception as e:
            last_err = str(e)
            continue

    return market_client, None, f"账户连接受限 (将执行模拟分析): {last_err[:120]}"


def fetch_global_macro_benchmarks():
    """
    段永平“机会成本基准”与巴菲特“无风险利率地心引力”数据引擎
    """
    benchmarks = {
        "US_10Y_Treasury_Yield": "^TNX",  # 十年期美债收益率 (资产定价之锚)
        "US_Dollar_Index": "DX-Y.NYB",    # 美元指数 (全球流动性松紧)
        "SP500_ETF": "SPY",               # 标普500基准
        "Nasdaq100_ETF": "QQQ",           # 纳斯达克科技基准
        "Berkshire_Hathaway": "BRK-B"     # 巴菲特旗舰作为价值锚定
    }
    macro_summary = {}
    for name, ticker in benchmarks.items():
        try:
            hist = yf.Ticker(ticker).history(period="1mo")
            if not hist.empty and len(hist) >= 5:
                latest = float(hist["Close"].iloc[-1])
                chg_5d = (latest / float(hist["Close"].iloc[-5]) - 1) * 100
                chg_20d = (latest / float(hist["Close"].iloc[0]) - 1) * 100
                macro_summary[name] = {
                    "latest": round(latest, 2),
                    "5d_change_pct": round(chg_5d, 2),
                    "20d_change_pct": round(chg_20d, 2)
                }
        except Exception as e:
            macro_summary[name] = {"error": str(e)}

    # 加密市场恐慌与贪婪指数 (7日均值趋势对比)
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=7", timeout=10).json()
        data = res.get("data", [])
        today_val = int(data[0]["value"])
        avg_7d = sum(int(x["value"]) for x in data) / len(data)
        fng = {
            "today_score": today_val,
            "sentiment_label": data[0]["value_classification"],
            "7d_avg_score": round(avg_7d, 1),
            "sentiment_delta": round(today_val - avg_7d, 1)
        }
    except Exception:
        fng = {"today_score": 50, "sentiment_label": "Neutral", "7d_avg_score": 50.0, "sentiment_delta": 0.0}

    return macro_summary, fng


def calc_wilders_rsi(series, period=14):
    """华尔街标准 Wilder's 平滑 RSI 算法"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def analyze_market_and_portfolio(market_client, trade_client):
    """计算 200日大周期估值指标，并自动扫描用户最新入金与持仓结构"""
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
        sma_50 = float(df["close"].tail(50).mean())
        sma_200 = float(df["close"].mean())
        high_200d = float(df["high"].max())
        low_200d = float(df["low"].min())

        # 梅耶倍数 (Mayer Multiple): 低于 0.85 为历史级低估，高于 1.6 为过热
        mayer_multiple = price / sma_200
        drawdown_pct = (price / high_200d - 1) * 100
        rsi_14 = calc_wilders_rsi(df["close"], 14)

        # 30日年化波动率与量能比
        returns = df["close"].pct_change().dropna()
        vol_30d_ann = float(returns.tail(30).std() * np.sqrt(365) * 100)
        vol_ratio = float(df["vol"].iloc[-1] / df["vol"].tail(20).mean())

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
            "annualized_volatility_30d_pct": round(vol_30d_ann, 1),
            "volume_vs_20d_avg_ratio": round(vol_ratio, 2),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "range_200d": f"{round(low_200d, 2)} - {round(high_200d, 2)}"
        }

    for coin in holdings:
        holdings[coin]["weight_pct"] = (
            round(holdings[coin]["market_value_usdt"] / total_equity_usdt * 100, 2)
            if total_equity_usdt > 0 else 0.0
        )

    portfolio = {
        "total_equity_usdt": round(total_equity_usdt, 2),
        "available_cash_usdt": round(free_cash, 2),
        "cash_weight_pct": round(free_cash / total_equity_usdt * 100, 2) if total_equity_usdt > 0 else 100.0,
        "positions": holdings
    }

    return market_metrics, portfolio


def invoke_value_investment_committee(macro, fng, market_metrics, portfolio):
    """
    召唤巴菲特、芒格、段永平三位一体 AI 投委会，输出严谨的结构化操盘指令
    """
    client = OpenAI(
        api_key=os.environ.get("LLM_API_KEY"),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    )

    system_prompt = """
    你是全权打理用户加密家族办公室的“巴菲特-芒格-段永平联合首席投资官 (CIO)”。
    用户只负责往账户入金 USDT，你负责全自动看盘、资产配置与调仓。
    请严格运用以下三位大师的量化映射准则进行决策：

    1. 【段永平：机会成本与本分 (Stop Doing List)】
       - 先看 10年期美债收益率 (^TNX) 与标普500/伯克希尔表现。若宏观流动性收紧且加密市场毫无安全边际，最佳动作就是 HOLD（按兵不动，零手续费磨损）。
       - 当用户刚入金导致现金比例极高（如 cash_weight_pct > 75%），且核心标的 Mayer Multiple < 1.15、RSI < 55 时，允许动用 5%~10% 现金开启温和底仓定投。

    2. 【巴菲特：棒球甜区与安全边际 (Margin of Safety)】
       - 黄金击球区 (重锤抄底)：当恐慌指数 < 28，或 Mayer Multiple < 0.90（跌破200日牛熊线），或自高点回撤超 -30% 且 RSI < 35 时，动用 12%~20% 可用现金果断买入。
       - 贪婪兑现区 (分批止盈)：当恐慌贪婪指数 > 76 且 RSI > 72、或 Mayer Multiple > 1.55 时，下达 SELL 指令，卖出 15%~35% 持仓换回 USDT 锁住利润。

    3. 【查理·芒格：逆向思考 (Invert, Always Invert)】
       - 在下达任何指令前，必须先指出当前如果盲目做多会死在哪里（列出最致命的宏观或结构性风险）。

    你必须严格且仅输出合法的 JSON 对象（不要包含任何多余文字），格式如下：
    {
      "market_regime": "黄金击球抄底区 / 合理价值定投区 / 垃圾时间观望区 / 极度贪婪止盈区",
      "macro_opportunity_cost_verdict": "结合美债收益率与美股基准的跨市场资金水位判断",
      "buffett_memo": "巴菲特视角关于当前安全边际与现金储备的点评",
      "munger_inversion_risk": "芒格毒舌逆向推演：当前最需要警惕的致败风险",
      "duan_stop_doing_note": "段永平今日不为清单提醒",
      "orders": [
        {
          "symbol": "BTC/USDT",
          "action": "BUY 或 SELL 或 HOLD",
          "allocation_ratio": 0.10,
          "conviction_score": 85,
          "thesis": "具体量化指标触发依据"
        }
      ]
    }
    规则说明：
    - orders 必须包含 BTC/USDT, ETH/USDT, SOL/USDT 三个标的。
    - BUY 时，allocation_ratio 表示动用【当前可用现金】的比例 (0.05 ~ 0.20)。
    - SELL 时，allocation_ratio 表示卖出【该币种当前可用持仓】的比例 (0.10 ~ 0.35)。
    - HOLD 时，allocation_ratio 必须为 0.0。
    """

    user_context = json.dumps({
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "global_macro_benchmarks": macro,
        "crypto_fear_and_greed": fng,
        "crypto_valuation_metrics": market_metrics,
        "current_portfolio": portfolio
    }, ensure_ascii=False, indent=2)

    response = client.chat.completions.create(
        model=os.environ.get("LLM_MODEL", "deepseek-chat"),
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_context}
        ],
        temperature=0.2
    )

    raw_text = response.choices[0].message.content.strip()
    # 剥离可能存在的 Markdown 代码块包裹，确保 JSON 100% 解析成功
    cleaned_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()
    return json.loads(cleaned_json)


def execute_with_risk_firewall(trade_client, ai_plan, market_metrics, portfolio):
    """
    五重硬风控防火墙校验与自动实盘下单执行器
    """
    live_flag = os.environ.get("LIVE_TRADING", "false").lower() == "true"
    can_trade_live = live_flag and (trade_client is not None)
    logs = []

    avail_cash = portfolio["available_cash_usdt"]
    total_equity = portfolio["total_equity_usdt"]
    cash_floor = total_equity * MIN_CASH_RESERVE_PCT

    for order in ai_plan.get("orders", []):
        symbol = order.get("symbol")
        action = str(order.get("action", "HOLD")).upper()
        ratio = float(order.get("allocation_ratio", 0.0))
        thesis = order.get("thesis", "")
        score = order.get("conviction_score", 50)

        if symbol not in market_metrics or action == "HOLD" or ratio <= 0:
            logs.append(f"⏸️ **{symbol}** | `HOLD (按兵不动)` | 信心分: `{score}` | 逻辑: {thesis}")
            continue

        price = market_metrics[symbol]["current_price"]
        base_coin = symbol.split("/")[0]
        current_weight = portfolio["positions"].get(base_coin, {}).get("weight_pct", 0.0) / 100.0

        if action == "BUY":
            # 防火墙 1：单一资产持仓集中度上限检查
            if current_weight >= MAX_SINGLE_ASSET_WEIGHT:
                logs.append(f"🛡️ **{symbol}** | `风控拦截` | 当前仓位占比 ({current_weight*100:.1f}%) 已达 50% 上限，禁止继续加仓。")
                continue

            # 防火墙 2：单次动用现金上限截断 (最高 20%)
            safe_ratio = min(ratio, MAX_CASH_PER_BUY_PCT)
            target_usdt = avail_cash * safe_ratio

            # 防火墙 3：巴菲特 15% 绝对现金底垫保护
            if (avail_cash - target_usdt) < cash_floor:
                target_usdt = max(0.0, avail_cash - cash_floor)

            # 防火墙 4：最小交易金额校验 (防止交易所拒单)
            if target_usdt < MIN_ORDER_VALUE_USDT:
                logs.append(
                    f"🛡️ **{symbol}** | `等待入金/余额不足` | AI 建议买入比例 `{safe_ratio*100:.0f}%` "
                    f"(约 `{target_usdt:.2f} USDT`)，未达最小下单门槛 `{MIN_ORDER_VALUE_USDT} USDT` | 逻辑: {thesis}"
                )
                continue

            raw_qty = target_usdt / price
            if can_trade_live:
                try:
                    precise_qty = float(trade_client.amount_to_precision(symbol, raw_qty))
                    res = trade_client.create_market_buy_order(symbol, precise_qty)
                    avail_cash -= target_usdt
                    logs.append(
                        f"✅ **{symbol}** | `实盘买入成交` | 数量: `{precise_qty}` | 耗资: `~{target_usdt:.2f} USDT` "
                        f"| 成交均价: `{price}` | OrderID: `{res.get('id')}` | 逻辑: {thesis}"
                    )
                except Exception as e:
                    logs.append(f"❌ **{symbol}** | `实盘买入报错` | 原因: `{str(e)[:120]}`")
            else:
                logs.append(
                    f"🧪 **{symbol}** | `模拟盘买入指令` | 拟买数量: `{raw_qty:.5f}` (`{target_usdt:.2f} USDT`) | 逻辑: {thesis}"
                )

        elif action == "SELL":
            free_qty = portfolio["positions"].get(base_coin, {}).get("free_qty", 0.0)
            safe_sell_ratio = min(ratio, MAX_SELL_PER_TRADE_PCT)
            sell_qty = free_qty * safe_sell_ratio
            est_usdt = sell_qty * price

            if est_usdt < MIN_ORDER_VALUE_USDT:
                logs.append(
                    f"🛡️ **{symbol}** | `止盈跳过` | 可售市值 (`{est_usdt:.2f} USDT`) 低于 `{MIN_ORDER_VALUE_USDT} USDT` 门槛。"
                )
                continue

            if can_trade_live:
                try:
                    precise_sell_qty = float(trade_client.amount_to_precision(symbol, sell_qty))
                    res = trade_client.create_market_sell_order(symbol, precise_sell_qty)
                    logs.append(
                        f"✅ **{symbol}** | `实盘止盈成交` | 卖出数量: `{precise_sell_qty}` | 回笼现金: `~{est_usdt:.2f} USDT` "
                        f"| OrderID: `{res.get('id')}` | 逻辑: {thesis}"
                    )
                except Exception as e:
                    logs.append(f"❌ **{symbol}** | `实盘卖出报错` | 原因: `{str(e)[:120]}`")
            else:
                logs.append(
                    f"🧪 **{symbol}** | `模拟盘止盈指令` | 拟卖数量: `{sell_qty:.5f}` (`~{est_usdt:.2f} USDT`) | 逻辑: {thesis}"
                )

    return logs


def generate_executive_report(conn_status, macro, fng, market_metrics, portfolio, ai_plan, logs):
    """生成家族办公室级 Markdown 投研与交割日报"""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    live_str = "🟢 实盘全自动托管激活" if os.environ.get("LIVE_TRADING", "false").lower() == "true" else "🟡 模拟巡航模式"

    # 构建行情估值表
    market_rows = []
    for sym, m in market_metrics.items():
        market_rows.append(
            f"| **{sym}** | `${m['current_price']}` | `{m['mayer_multiple_price_to_sma200']}x` | "
            f"`{m['drawdown_from_200d_high_pct']}%` | `{m['wilders_rsi_14d']}` | `${m['sma_200']}` |"
        )
    market_table = "\n".join(market_rows)

    # 构建持仓明细表
    pos_rows = []
    for coin, p in portfolio["positions"].items():
        pos_rows.append(f"| **{coin}** | `{p['total_qty']}` | `${p['market_value_usdt']} USDT` | `{p['weight_pct']}%` |")
    pos_table = "\n".join(pos_rows)

    us10y = macro.get("US_10Y_Treasury_Yield", {}).get("latest", "N/A")
    spy_chg = macro.get("SP500_ETF", {}).get("5d_change_pct", "N/A")
    brk_chg = macro.get("Berkshire_Hathaway", {}).get("5d_change_pct", "N/A")

    report = f"""# 🏛️ 巴芒段 AI 家族办公室 · 全自动资产配置与交割日报
> **执行时间**：`{now_str}` ｜ **引擎状态**：**{live_str}** ｜ **通道状态**：`{conn_status}`

---

## 一、 账户净值与入金感知快照
* **账户总净值 (Total Equity)**：`${portfolio['total_equity_usdt']} USDT`
* **可用现金池 (Available Cash)**：`${portfolio['available_cash_usdt']} USDT` （现金仓位占比：`{portfolio['cash_weight_pct']}%`）
* **加密情绪温度计 (Fear & Greed)**：今日 `{fng['today_score']}` ({fng['sentiment_label']}) ｜ 7日均值：`{fng['7d_avg_score']}`
* **跨市场机会成本锚定**：10年期美债收益率 `{us10y}%` ｜ 标普500近5日 `{spy_chg}%` ｜ 伯克希尔(BRK.B)近5日 `{brk_chg}%`

| 持仓资产 | 持仓数量 | 折合市值 (USDT) | 占总净值权重 |
| :--- | :--- | :--- | :--- |
{pos_table}

---

## 二、 核心标的 200日大周期估值矩阵
| 交易对 | 最新价格 | 梅耶倍数 (现价/200日线) | 距200日高点回撤 | 14日 Wilder's RSI | 200日牛熊分界线 |
| :--- | :--- | :--- | :--- | :--- | :--- |
{market_table}

---

## 三、 巴菲特 · 芒格 · 段永平 投委会共识决议
* 🎯 **当前市场周期定调**：**`{ai_plan.get('market_regime', 'N/A')}`**
* 🌐 **全球宏观与机会成本裁决**：{ai_plan.get('macro_opportunity_cost_verdict', '')}
* 🎩 **沃伦·巴菲特 (安全边际评估)**：{ai_plan.get('buffett_memo', '')}
* 👓 **查理·芒格 (逆向风险压力测试)**：{ai_plan.get('munger_inversion_risk', '')}
* ♟️ **段永平 (本分与今日不为清单)**：{ai_plan.get('duan_stop_doing_note', '')}

---

## 四、 全自动交易指令与风控护栏回执
""" + "\n".join(f"- {item}" for item in logs) + "\n"

    with open("LATEST_CIO_MEMO.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(report)


if __name__ == "__main__":
    market_client, trade_client, conn_status = init_smart_exchange()
    macro, fng = fetch_global_macro_benchmarks()
    market_metrics, portfolio = analyze_market_and_portfolio(market_client, trade_client)
    ai_plan = invoke_value_investment_committee(macro, fng, market_metrics, portfolio)
    logs = execute_with_risk_firewall(trade_client, ai_plan, market_metrics, portfolio)
    generate_executive_report(conn_status, macro, fng, market_metrics, portfolio, ai_plan, logs)
