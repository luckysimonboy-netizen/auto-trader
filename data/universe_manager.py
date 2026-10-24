import yfinance as yf
import pandas as pd
from utils.logger import setup_logger
from data.cleaner_and_adjuster import DataCleanerAndAdjuster
from data.storage_engine import HybridStorageEngine

logger = setup_logger("UniverseManager")

class USDataAndUniverseManager:
    def __init__(self):
        self.storage = HybridStorageEngine()
        self.blacklist = {"BBBYQ", "LUCKQ", "SIVBQ"}

    def filter_universe(self, symbols: list[str]) -> list[str]:
        """剔除黑名单、粉单(OTC)与破产股(Q结尾)"""
        valid = []
        for s in symbols:
            s_up = s.strip().upper()
            if s_up in self.blacklist or (len(s_up) == 5 and s_up.endswith("Q")) or ".PK" in s_up:
                logger.warning(f"标的 {s_up} 命中风险/退市黑名单，自动拦截！")
                continue
            valid.append(s_up)
        return valid

    def download_and_sync(self, symbols: list[str], start_date: str = "2023-01-01", interval: str = "1d", adjust_type: str = "qfq") -> dict:
        clean_symbols = self.filter_universe(symbols)
        result = {}
        
        for sym in clean_symbols:
            logger.info(f"正在下载 {sym} ({interval}) 行情...")
            try:
                ticker = yf.Ticker(sym)
                df = ticker.history(start=start_date, interval=interval, auto_adjust=False, actions=True)
                if df.empty:
                    continue
                df = df.reset_index()
                t_col = "Datetime" if "Datetime" in df.columns else "Date"
                df["timestamp"] = pd.to_datetime(df[t_col]).dt.strftime("%Y-%m-%d" if interval == "1d" else "%Y-%m-%d %H:%M:%S")
                df["symbol"] = sym
                df["interval"] = interval
                df = df.rename(columns={
                    "Open": "open", "High": "high", "Low": "low", "Close": "close",
                    "Volume": "volume", "Dividends": "dividends", "Stock Splits": "splits"
                })
                
                # 清洗与复权
                cleaned = DataCleanerAndAdjuster.clean_ohlcv(df)
                adjusted = DataCleanerAndAdjuster.apply_adjustment(cleaned, adjust_type)
                
                # 入库持久化
                self.storage.save_data(adjusted)
                result[sym] = adjusted
            except Exception as e:
                logger.error(f"下载 {sym} 出错: {e}")
                
        return result
