# VELTRIX instrument scope — XAUUSD only

## Binding product rule

VELTRIX AI analysis and scalping are restricted to the XAUUSD gold contract. No other instrument may enter market-data collection, feature generation, strategy research, signal generation, risk allocation, or execution.

- Canonical instrument: `XAUUSD`.
- Broker-specific suffixes (for example `XAUUSDm`) are accepted only after contract metadata confirms base currency XAU and profit currency USD.
- XAGUSD, other metals, forex, crypto, indices, and synthetic instruments are out of scope and must fail closed.
- Historical XAGUSD records are retained as archival evidence but are not eligible for active research, model training, inference, or certification.
- All strategy features, thresholds, and validation results are calibrated solely against XAUUSD data.
- A missing, stale, malformed, ambiguous, or incorrectly mapped XAUUSD quote blocks analysis and any future order intent.

## Safety and execution

Data collection remains read-only and requires a verified Exness DEMO account with terminal trading and DLL permissions disabled. Future order execution remains disabled until independent validation. When implemented, execution must independently verify DEMO identity, exact XAUUSD contract mapping, quote freshness, spread, risk limits, protective stops, emergency stop, and broker reconciliation. Live/real-money execution remains prohibited.

## Migration rule

Existing dual-instrument datasets and reports are not deleted. They are marked legacy/out-of-scope and cannot be mixed into XAUUSD-only datasets or certification. New collection and analysis pipelines must produce XAUUSD-only artifacts.
