# ==============================================================================
# 🏛️ 模块三：赛博投委会多 Agent 交叉审判与决策中枢 (Committee Agent)
# ==============================================================================

class CyberInvestmentCommittee:
    """赛博投委会：多 Agent 智能集成与风控一票否决中枢"""
    
    @staticmethod
    def evaluate_ticker(ticker: str, factors: dict) -> dict:
        current_price = factors["close"]
        rsi = factors["rsi"]
        lower_bb = factors["lower_band"]
        bias = factors["bias"]
        volatility = factors["volatility"]
        
        # Agent 1：动量超卖审判官 (RSI Agent)
        agent_rsi_vote = "BUY" if rsi <= 35.0 else ("SELL" if rsi >= 68.0 else "HOLD")
        
        # Agent 2：波动率与空间猎手 (Bollinger & BIAS Agent)
        agent_space_vote = "BUY" if (current_price <= lower_bb or bias <= -3.5) else "HOLD"
        
        # Agent 3：风控与波动率熔断官 (Risk Management Agent)
        agent_risk_vote = "PASS" if volatility < 80.0 else "VETO (年化波动率过高熔断)"
        
        # 投委会集成评分机制
        score = 0
        reasons = []
        
        if agent_rsi_vote == "BUY":
            score += 1
            reasons.append(f"RSI动能超卖({rsi:.1f})")
        else:
            reasons.append(f"RSI中性({rsi:.1f})")
            
        if agent_space_vote == "BUY":
            score += 1
            reasons.append("触及布林下轨/乖离超跌")
        else:
            reasons.append("空间运行平稳")
            
        if "VETO" in agent_risk_vote:
            score = 0
            reasons.append("⚠️ 触发风控一票否决")
        
        # 投委会最终裁决
        if score >= 2:
            final_signal = "🔥 赛博投委会绝杀 BUY"
        elif agent_rsi_vote == "SELL":
            final_signal = "⚠️ 超热清仓 SELL"
        else:
            final_signal = "⏸️ 动态观望 HOLD"
            
        return {
            "ticker": ticker.replace("-USD", "/USDT"),
            "price": round(current_price, 2),
            "rsi": round(rsi, 1),
            "bias": round(bias, 2),
            "volatility": round(volatility, 2),
            "score": score,
            "signal": final_signal,
            "reason": " | ".join(reasons)
        }

    @classmethod
    def convene_committee(cls, factors_cache: dict) -> list:
        """召集赛博投委会，对全市场因子矩阵进行交叉审判与排序"""
        print("🏛️ [Cyber Committee] 赛博投委会正在召集全体 Agent 进行多维交叉审判...")
        committee_decisions = []
        
        for ticker, factors in factors_cache.items():
            decision = cls.evaluate_ticker(ticker, factors)
            committee_decisions.append(decision)
            
        # 按投委会共振得分降序排列，杀伤力最强的标的排在最前
        committee_decisions.sort(key=lambda x: x["score"], reverse=True)
        print(f"✅ [Cyber Committee] 审判完毕，已生成全景阿尔法狙击排行榜。")
        return committee_decisions

if __name__ == "__main__":
    from data_pipeline import MarketDataPipeline
    from factor_engine import AlphaFactorFactory
    
    cache = MarketDataPipeline.run_pipeline()
    factors = AlphaFactorFactory.batch_process(cache)
    decisions = CyberInvestmentCommittee.convene_committee(factors)
    print("投委会头号猎物决议示例：", decisions[:1])
