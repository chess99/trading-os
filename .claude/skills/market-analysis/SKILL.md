---
name: market-analysis
description: Comprehensive market analysis including trend identification, technical indicators, sector rotation, and investment opportunity screening. Use when analyzing markets, identifying trends, or researching investment opportunities.
---

# Market Analysis Skill

## Overview

This skill provides comprehensive market analysis capabilities for investment decision making. It combines technical analysis, fundamental analysis, and market sentiment evaluation to generate actionable investment insights.

## Core Capabilities

### 1. Technical Analysis
- Trend identification and momentum analysis
- Technical indicator calculation (RSI, MACD, Bollinger Bands)
- Support and resistance level identification
- Volume analysis and market breadth assessment

### 2. Sector Analysis
- Sector rotation detection
- Relative sector performance analysis
- Industry trend identification
- Sector allocation recommendations

### 3. Market Sentiment
- Market phase identification (bull/bear/sideways)
- Volatility assessment
- Risk-on/risk-off sentiment analysis
- Market breadth indicators

### 4. Investment Screening
- Growth stock identification
- Value stock screening
- Momentum stock detection
- Dividend yield analysis

## Quick Start

```bash
# Run comprehensive market analysis
python scripts/market_analysis.py

# Analyze specific sectors
python scripts/sector_analysis.py --sectors technology,healthcare,finance

# Screen for investment opportunities
python scripts/investment_screening.py --criteria growth,value
```

## Analysis Framework

### Market Phase Identification
1. **Bull Market Indicators**
   - Broad market uptrend
   - High market breadth
   - Low volatility
   - Risk-on sentiment

2. **Bear Market Indicators**
   - Broad market downtrend
   - Declining market breadth
   - High volatility
   - Risk-off sentiment

3. **Sideways Market**
   - Range-bound trading
   - Mixed signals
   - Moderate volatility
   - Neutral sentiment

### Sector Rotation Analysis
- **Early Cycle**: Technology, Consumer Discretionary
- **Mid Cycle**: Industrials, Materials
- **Late Cycle**: Energy, Financials
- **Recession**: Utilities, Consumer Staples, Healthcare

### Investment Opportunity Screening
- **Growth Criteria**: Revenue growth >15%, Earnings growth >20%
- **Value Criteria**: P/E <15, P/B <1.5, Dividend yield >3%
- **Momentum Criteria**: Price above 50/200 MA, RSI 50-70
- **Quality Criteria**: ROE >15%, Debt/Equity <0.5

## Output Format

All analysis outputs follow a standardized format:

```json
{
  "timestamp": "2026-01-28T17:00:00Z",
  "analysis_type": "market_overview",
  "market_phase": "bull_market",
  "confidence": 0.85,
  "key_findings": [
    "Technology sector leading market",
    "Strong momentum indicators",
    "Low volatility environment"
  ],
  "recommendations": [
    "Maintain growth allocation",
    "Consider tech sector exposure",
    "Monitor volatility levels"
  ],
  "risk_factors": [
    "Potential valuation concerns",
    "Interest rate sensitivity"
  ]
}
```

## Advanced Features

### Custom Indicators
The skill includes proprietary indicators:
- **Market Regime Indicator**: Combines multiple signals to identify market phases
- **Sector Rotation Signal**: Identifies optimal sector allocation timing
- **Opportunity Score**: Ranks investment opportunities across multiple criteria

### Integration Points
- **Data Sources**: Integrates with trading-os data lake
- **Risk Management**: Coordinates with risk assessment systems
- **Portfolio Management**: Provides input for allocation decisions

## Best Practices

1. **Regular Updates**: Run analysis daily for current market conditions
2. **Multiple Timeframes**: Consider both short-term and long-term trends
3. **Cross-Validation**: Verify signals across different indicators
4. **Risk Awareness**: Always consider downside risks and market volatility
5. **Documentation**: Record analysis rationale and decision factors

This skill is designed to be the foundation of professional investment analysis, providing the market intelligence needed for informed investment decisions.