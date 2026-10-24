import os
import json
import concurrent.futures
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone

# ==============================================================================
# 🏛️ 模块一：全景多源数据采集与高并发管道 (Data Pipeline)
# ==============================================================================
UNIVERSE_POOL = [
    "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", 
    "AMD", "COIN", "NFLX", "PLTR", "SPY", "QQQ", "VOOG",
    "BTC-USD", "ETH-USD", "SOL-USD"
]

class MarketDataPipeline:
    """全球多市场高并发数据采集与清洗管道"""
    
    @staticmethod
    def fetch_ticker_history(ticker: str) -> pd.DataFrame:
        try:
            # 采用 3 个月 1 小时级别高频数据进行全景扫描
            hist = yf.Ticker(ticker).history(period="3mo", interval="1h")
            if hist.empty or len(hist) < 30:
                return None
            return hist["Close"]
        except Exception:
            return None

    @classmethod
    def run_pipeline(cls) -> dict:
        print(f"🚀 [Pipeline] 正在高并发拉取全球资产池行情，标的总数: {len(UNIVERSE_POOL)}...")
        raw_data_cache = {}
        
        # 使用高并发线程池瞬间吞吐海量行情数据
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_ticker = {executor.submit(cls.fetch_ticker_history, t): t for t in UNIVERSE_POOL}
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                series = future.result()
                if series is not None:
                    raw_data_cache[ticker] = series
                    
        print(f"✅ [Pipeline] 数据管道吞吐完毕，成功加载 {len(raw_data_cache)} 只标的资产流。")
        return raw_data_cache

if __name__ == "__main__":
    cache = MarketDataPipeline.run_pipeline()
    print("当前已就绪的资产列表：", list(cache.keys()))
