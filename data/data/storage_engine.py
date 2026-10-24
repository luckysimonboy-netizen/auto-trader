import os
import sqlite3
import pandas as pd
from utils.logger import setup_logger

logger = setup_logger("StorageEngine")

class HybridStorageEngine:
    def __init__(self, db_dir: str = "storage", db_name: str = "market_data.db"):
        self.db_dir = db_dir
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, db_name)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv_data (
                    symbol TEXT, timestamp TEXT, interval TEXT,
                    open REAL, high REAL, low REAL, close REAL, raw_close REAL,
                    volume INTEGER, dividends REAL, splits REAL,
                    qfq_factor REAL, hfq_factor REAL,
                    PRIMARY KEY (symbol, timestamp, interval)
                )
            """)
            conn.commit()

    def save_data(self, df: pd.DataFrame):
        if df.empty:
            return
        symbol = df["symbol"].iloc[0]
        interval = df["interval"].iloc[0]
        
        # 大于5万行自动切换为高效 Parquet 存储
        if len(df) >= 50000:
            parquet_path = os.path.join(self.db_dir, f"{symbol}_{interval}.parquet")
            df.to_parquet(parquet_path, index=False)
            logger.info(f"[{symbol}] 行数达 {len(df)}，已自动切换写入 Parquet: {parquet_path}")
            return

        with sqlite3.connect(self.db_path) as conn:
            records = df[[
                "symbol", "timestamp", "interval", "open", "high", "low", "close",
                "raw_close", "volume", "dividends", "splits", "qfq_factor", "hfq_factor"
            ]].to_records(index=False)
            conn.executemany("""
                INSERT OR REPLACE INTO ohlcv_data
                (symbol, timestamp, interval, open, high, low, close, raw_close, volume, dividends, splits, qfq_factor, hfq_factor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, list(records))
            conn.commit()
        logger.info(f"[{symbol}] 成功增量入库 SQLite: {len(df)} 条")

    def load_data(self, symbol: str, interval: str = "1d", start_date: str = None) -> pd.DataFrame:
        parquet_path = os.path.join(self.db_dir, f"{symbol}_{interval}.parquet")
        if os.path.exists(parquet_path):
            df = pd.read_parquet(parquet_path)
            return df[df["timestamp"] >= start_date] if start_date else df
            
        with sqlite3.connect(self.db_path) as conn:
            sql = "SELECT * FROM ohlcv_data WHERE symbol = ? AND interval = ?"
            params = [symbol, interval]
            if start_date:
                sql += " AND timestamp >= ?"
                params.append(start_date)
            sql += " ORDER BY timestamp ASC"
            return pd.read_sql_query(sql, conn, params=params)
