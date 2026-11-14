# Multi-position XAUUSD portfolio simulator

## Scope

`tools/mt5_xauusd_multi_position_simulator.py` is an offline research simulator. It accepts a verified quote stream, event proposals from a separately validated signal source, broker symbol economics, and explicit risk settings. It does not create or send orders. It is isolated from the preregistered Phase 8 evaluator.

## Event contract

The input JSON object contains an `events` array. Each event requires:

- `signal_id`: unique stable identifier.
- `candidate_id`: source candidate/configuration identifier.
- `signal_window_end_msc`: UTC epoch milliseconds; entry is the first quote strictly later.
- `direction`: `long` or `short`.
- `hold_seconds`: integer from 10 through 60.
- `stop_distance_price`: positive XAUUSD price distance.
- `take_profit_distance_price`: positive XAUUSD price distance.

The simulator does not generate candidate signals or tune stop/target distances. The upstream strategy must provide them using information available at the signal timestamp.

## Broker specification contract

The broker snapshot must provide:

- `point_size`, `tick_size`, `tick_value_loss`.
- `volume_min`, `volume_max`, `volume_step`.
- `margin_per_lot`: a broker-calculated, time-stamped margin estimate per lot for the relevant XAUUSD contract and account leverage.

Do not infer contract size, tick economics, or margin from generic XAUUSD assumptions. The simulator requires explicit values. A static `margin_per_lot` snapshot is an approximation; live preflight must independently call the broker's current margin calculator for every proposed volume.

The CLI accepts a wrapper with `account_mode: DEMO`, `trading_enabled: false`, and `instrument_specs.XAUUSD`. The symbol/account metadata must come from a provenance-verified Exness DEMO snapshot before research reports can be treated as broker-specific.

## Risk configuration

Required fields:

- `equity`
- `risk_per_trade_percent` (positive, no greater than 0.25)
- `max_portfolio_risk_percent` (positive, no greater than 0.50)
- `initial_free_margin`
- `margin_reserve_money`

For each entry, volume is the lesser of the per-trade risk budget and remaining aggregate open-stop-risk capacity, divided by loss-per-lot. Volume is rounded down to the broker step. The trade is rejected if the minimum broker volume would breach the risk budget or if the margin reserve would be violated.

There is no fixed maximum number of simultaneous positions. The portfolio risk budget, free margin, and broker volume constraints are the binding limits. Every open or unresolved position continues to reserve its stop-risk and margin until a simulated close is confirmed; data gaps do not release exposure.

## Exit model

- Long entry: ask plus entry slippage; long exit: bid minus exit slippage.
- Short entry: bid minus entry slippage; short exit: ask plus exit slippage.
- SL and TP are evaluated on the executable side of the quote.
- If neither is touched, the first quote at/after the 10-60 second time deadline is used, subject to the configured exit tolerance.
- A quote gap beyond the freshness limit or a missing deadline quote leaves the position unresolved and reserves exposure.
- Observed bid/ask crossing includes spread once. Slippage is an explicit sensitivity assumption, not measured execution quality.
- Commission remains unverified; net PnL is always null and net-performance claims remain disabled.

A stop can be crossed between recorded ticks. This tick-only simulator cannot reconstruct intratick paths or guarantee stop fill price. Gaps can therefore produce worse real fills than the theoretical result.

## Running

```bash
python -m tools.mt5_xauusd_multi_position_simulator \
  --ticks path/to/ticks.json \
  --events path/to/events.json \
  --broker-spec path/to/verified_demo_snapshot.json \
  --risk-config path/to/risk_config.json \
  --slippage-points-per-side 2 \
  --output path/to/portfolio_report.json
```

The ticks JSON is an array of objects with `time_msc`, `bid`, and `ask`. The event file contains an `events` array. The broker snapshot and risk config are separate JSON files.

## Safety boundary and current limits

- No execution APIs, terminal connection, credentials, or broker requests are used.
- No daily trade-count cap or profit cap is introduced.
- The existing MQL5 risk-control module currently retains its 1.00% daily loss hard ceiling, 0.25% per-trade ceiling, 0.50% aggregate open-risk ceiling, cooldown, and consecutive-loss lock. The requested 50-60% daily loss threshold is not substituted for these controls.
- The legacy `NexoraScalper.mq5` prototype contains a disabled order-send path and is not the VELTRIX strategy integration target. Keep `EnableDemoOrders=false` and `EmergencyStop=true`; do not attach it for this research task.
- Phase 8 remains frozen with one position per candidate configuration. Multi-position portfolio results are a separate research track and cannot be substituted for Phase 8 evidence.
- This simulator is not certified for DEMO forward validation or execution. Its event source, broker snapshot provenance, commission, and prospective multi-position performance still require validation.
