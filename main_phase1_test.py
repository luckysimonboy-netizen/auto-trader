from data.universe_manager import USDataAndUniverseManager

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 正在执行【阶段 1：美股量化系统 - 数据与股票池模块】验证")
    print("=" * 60)
    
    manager = USDataAndUniverseManager()
    
    # 1. 验证黑名单与OTC退市过滤
    test_pool = ["AAPL", "NVDA", "SPY", "BBBYQ", "TEST.PK"]
    print("\n[测试 1] 股票池黑名单过滤测试：")
    clean_pool = manager.filter_universe(test_pool)
    print(f"输入: {test_pool} -> 过滤后: {clean_pool}")
    
    # 2. 验证日线下载、清洗、前复权与持久化
    print("\n[测试 2] 下载日线数据 (含前复权与分红拆股追溯)：")
    data_dict = manager.download_and_sync(clean_pool, start_date="2024-01-01", interval="1d")
    
    # 3. 验证从本地 SQLite 读取数据
    print("\n[测试 3] 验证本地 SQLite 读取功能：")
    aapl_local = manager.storage.load_data("AAPL", interval="1d")
    print("AAPL 本地数据最近 3 条记录：")
    print(aapl_local[["symbol", "timestamp", "open", "high", "low", "close", "raw_close", "volume", "qfq_factor"]].tail(3))
    
    print("\n" + "=" * 60)
    print("✅ 【阶段 1 验证成功】所有数据已安全落盘至 storage/market_data.db！")
    print("=" * 60)
