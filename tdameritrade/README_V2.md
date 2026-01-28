# Trading Bot V2 - Architecture Documentation

## Overview

This is a complete refactoring of the trading bot with a modular, production-ready architecture. The bot now supports:

- **Charles Schwab API** (replacing TD Ameritrade)
- **Stabilized core model layer** with proper lifecycle management
- **Strategy layer** with VP zones, ADD regime, FVG detection, and ATR classification
- **Butterfly and strangle strategies** with conversion logic
- **Risk management** with account limits and behavior lockouts
- **Position management** with autonomous exit/adjustment logic
- **Data feeds** for live market data
- **Structured logging and journaling**
- **Optional GenAI integration** for narrative explanations

## Architecture

### Core Components

#### 1. Core Model Layer (`account.py`)
- **Account**: Tracks balance, positions, and groups
- **Group**: Multi-leg option strategies (spreads, butterflies, strangles)
- **Option**: Individual option leg with lifecycle management

**Key Features:**
- Instance attributes (no shared state)
- Standardized pricing conventions (credit/debit, signs)
- Lifecycle invariants (opendt/closedt, is_open checks)
- Source of truth for pricing (bid/ask/mark with slippage handling)

#### 2. Broker Adapter (`engine/broker.py`)
- **BrokerAdapter**: Abstract interface for broker APIs
- **CharlesSchwabAdapter**: Charles Schwab API implementation
- **PaperBrokerAdapter**: Paper trading simulation

**Methods:**
- `get_quote()`, `get_chain()`, `place_order()`, `replace_order()`, `cancel_order()`
- `get_positions()`, `get_fills()`, `get_account_info()`

#### 3. Execution Engine (`engine/execution.py`)
- Converts strategy decisions into broker orders
- Handles multi-leg orders with fallback to individual legs
- Supports OCO orders (where broker supports)

#### 4. Strategy Layer

**Filters (`strategies/filters.py`):**
- **VPZoneDetector**: Volume Profile zone detection (POC, value area)
- **ADDRegimeClassifier**: Accumulation/Distribution/Distribution regime
- **FVGDetector**: Fair Value Gap detection
- **ATRRegimeClassifier**: Volatility regime based on ATR
- **NoTradeFilter**: News windows, chop detection, volatility spikes

**Butterflies (`strategies/butterflies.py`):**
- **ButterflyBuilder**: Builds directional OTM flies and broken-wing flies
- **ButterflyEntryRules**: Entry conditions (VP + FVG + ADD alignment)
- **ButterflyManagement**: Profit targets, stops, roll logic, salvage

**Strangles (`strategies/strangles.py`):**
- **StrangleBuilder**: Builds IV decay strangles
- **StrangleEntryRules**: Entry conditions for neutral strategies
- **StrangleRiskTriggers**: Threatened side detection

**Conversion (`strategies/conversion.py`):**
- **StrategyConverter**: Converts strangles to butterflies/flies
- Profit booking and loss reduction logic

#### 5. Risk Management (`engine/risk.py`)
- **RiskGovernor**: Enforces account limits and behavior constraints
- Daily/weekly max loss
- Max open risk (buying power)
- Trade cooldowns
- Loss-triggered pauses (2 losses → 60 min pause)
- Position sizing (fixed dollar or volatility-adjusted)

#### 6. Position Manager (`engine/manager.py`)
- **PositionManager**: Autonomous trade management
- Monitors all open positions
- Evaluates exit conditions (price-based, VP break, FVG invalidation, time-based)
- Executes actions (close, roll, adjust, convert)

#### 7. Strategy Selector (`engine/selector.py`)
- **StrategySelector**: Chooses strategy mode based on regime
- Modes: STRANGLE, BUTTERFLY_BULLISH, BUTTERFLY_BEARISH, NO_TRADE
- Applies account policies (TOS = aggressive, FIDELITY = conservative)

#### 8. Data Feeds (`data/feeds.py`)
- **PriceFeed**: Real-time price data with candle aggregation
- **VIXFeed**: Volatility index feed
- **EconomicCalendarFeed**: Economic events (manual for now)
- **DataAggregator**: Combines feeds and computes indicators

#### 9. Logging & Journaling (`logs/journal.py`)
- **TradeJournal**: Structured JSON logging
- Decision logging (signals, strategy selection, orders, positions)
- Daily summaries with win rate, violations, missed setups
- **ReplayHarness**: Replay recorded days for testing

#### 10. GenAI Integration (`engine/genai.py`)
- **GenAIAnalyst**: Optional AI-powered analysis
- Narrative explanations for entries/exits
- Post-trade reviews with pattern extraction
- Contradiction detection vs trading rules
- Weekly improvement suggestions

## Configuration

### TOS Configuration (`config/config_tos.yaml`)
Aggressive settings:
- Tighter stops (180%)
- Higher risk limits
- More trades per day

### Fidelity Configuration (`config/config_fidelity.yaml`)
Conservative settings:
- Wider stops (250%)
- Lower risk limits
- Fewer trades per day
- VIX scaling for position sizing

## Usage

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export SCHWAB_CLIENT_ID="your_client_id"
export SCHWAB_REFRESH_TOKEN="your_refresh_token"
export OPENAI_API_KEY="your_openai_key"  # Optional, for GenAI features
```

3. Configure broker credentials in config file or use environment variables.

### Running the Bot

**Paper Trading (default):**
```bash
python main.py --config config/config_tos.yaml
```

**Live Trading:**
Edit config file to set `paper_mode: false` and ensure credentials are correct.

**Force Paper Mode:**
```bash
python main.py --config config/config_tos.yaml --paper
```

### Main Loop Flow

1. **Fetch Data**: Price, volume, VIX, options chain
2. **Compute Indicators**: ATR, volume profile, VP zones, FVGs
3. **Manage Positions**: Check exit conditions, execute actions
4. **Check Risk**: Verify account limits and cooldowns
5. **Select Strategy**: Choose mode based on regime
6. **Build Strategy**: Create Group with option legs
7. **Size Position**: Calculate contracts based on risk
8. **Execute**: Place order via execution engine
9. **Log**: Record decision in journal

## Key Features

### Lifecycle Management
- All positions have clear open/close states
- Timestamps for entry/exit tracking
- Validation before state transitions

### Pricing Conventions
- **SHORT positions**: Positive = credit received, negative = cost to close
- **LONG positions**: Negative = debit paid, positive = value to sell
- **Group prices**: Net sum of all legs (already signed)

### Risk Controls
- Hard daily stop (configurable)
- Trade cooldowns
- Max open risk limits
- Forced EOD close for 0DTE

### Strategy Selection Logic
- **Strangle**: BALANCED/CHOP regime + reasonable IV
- **Butterfly Bullish**: ACCUMULATION regime + VP + FVG alignment
- **Butterfly Bearish**: DISTRIBUTION regime + VP + FVG alignment
- **No Trade**: Unsafe conditions (news, chop, volatility spikes)

## File Structure

```
.
├── account.py              # Core model layer
├── main.py                 # Main execution loop
├── engine/
│   ├── broker.py          # Broker adapters
│   ├── execution.py       # Order execution
│   ├── risk.py            # Risk management
│   ├── manager.py         # Position management
│   ├── selector.py        # Strategy selection
│   └── genai.py           # GenAI integration
├── strategies/
│   ├── filters.py         # Market filters
│   ├── butterflies.py     # Butterfly strategies
│   ├── strangles.py       # Strangle strategies
│   └── conversion.py      # Strategy conversion
├── data/
│   └── feeds.py           # Market data feeds
├── logs/
│   └── journal.py         # Logging and journaling
└── config/
    ├── config_tos.yaml     # TOS configuration
    └── config_fidelity.yaml # Fidelity configuration
```

## Migration from TD Ameritrade

The bot has been migrated from TD Ameritrade to Charles Schwab:

1. **API Endpoints**: Updated to Schwab endpoints
2. **Authentication**: OAuth2 with refresh tokens (similar flow)
3. **Data Structures**: Adapted to Schwab response formats
4. **Rate Limiting**: 120 requests/minute (same as TDA)

**Note**: You'll need to:
- Get Charles Schwab API credentials
- Update environment variables
- Test in paper mode first

## Testing

1. **Paper Trading**: Run with `paper_mode: true` for 2-4 weeks
2. **Replay Harness**: Test changes against recorded data
3. **Unit Tests**: (To be added) Test individual components

## Future Enhancements

- [ ] Full options chain parsing
- [ ] More sophisticated position sizing
- [ ] Additional strategy types
- [ ] Automated economic calendar
- [ ] Backtesting framework
- [ ] Web dashboard for monitoring

## Notes

- GenAI features are optional and require OpenAI API key
- Paper trading is recommended for initial testing
- All trading decisions are logged for analysis
- Risk limits should be configured based on account size and risk tolerance
