import numpy as np
import pandas as pd

# ==============================================================================
# 🏛️ 模块二：高性能阿尔法因子与特征工程工厂 (Factor Engine)
# ==============================================================================

class AlphaFactorFactory:
    """全球多市场量化特征与多维因子挖掘核心"""
    
    @staticmethod
    def compute_technical_factors(series: pd.Series) -> dict:
        if len(series) < 30:
            return {}
            
        # 1. 14周期 Wilder's RSI 动量因子
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        # 2. 布林带 (Bollinger Bands) 波动通道因子
        sma_20 = series.rolling(window=20).mean()
        std_20 = series.rolling(window=20).std()
        upper_band = sma_20 + (std_20 * 2)
        lower_band = sma_20 - (std_20 * 2)
        
        # 3. 乖离率 (BIAS) 深度超跌因子
        bias = ((series - sma_20) / sma_20) * 100
        
        # 4. 年化波动率 (Volatility) 风险因子
        volatility = series.pct_change().rolling(window=20).std() * np.sqrt(252) * 100

        return {
            "close": float(series.iloc[-1]),
            "rsi": float(rsi.iloc[-1]),
            "sma_20": float(sma_20.iloc[-1]),
            "upper_band": float(upper_band.iloc[-1]),
            "lower_band": float(lower_band.iloc[-1]),
            "bias": float(bias.iloc[-1]),
            "volatility": float(volatility.iloc[-1]) if not np.isnan(volatility.iloc[-1]) else 0.0
        }

    @classmethod
    def batch_process(cls, raw_data_cache: dict) -> dict:
        """批量对全市场资产池进行因子清洗与提取"""
        print("⚙️ [Factor Engine] 正在对全景资产池进行高性能阿尔法因子矩阵计算...")
        factors_cache = {}
        
        for ticker, series in raw_data_cache.items():
            factors = cls.compute_technical_factors(series)
            if factors:
                factors_cache[ticker] = factors
                
        print(f"✅ [Factor Engine] 阿尔法因子计算完毕，成功生成 {len(factors_cache)} 组结构化特征矩阵。")
        return factors_cache

if __name__ == "__main__":
    from data_pipeline import MarketDataPipeline
    cache = MarketDataPipeline.run_pipeline()
    factors = AlphaFactorFactory.batch_process(cache)
    print("因子样本身分示例：", list(factors.items())[:1])
