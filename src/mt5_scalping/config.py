"""Environment configuration with conservative, fail-closed trading defaults."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    metaapi_token: str = Field(default="", repr=False)
    metaapi_account_id: str = ""
    trading_mode: str = "disabled"
    allow_order_submission: bool = False
    allow_live_trading: bool = False
    symbols: str = "XAUUSD"
    max_spread_points: float = 0.0
    max_risk_per_trade_percent: float = 0.25
    max_daily_loss_percent: float = 1.0
    max_open_positions: int = 1

    @property
    def credentials_configured(self) -> bool:
        return bool(self.metaapi_token.strip() and self.metaapi_account_id.strip())

    @property
    def execution_enabled(self) -> bool:
        # Live trading is deliberately impossible in this initial scaffold.
        return (
            self.credentials_configured
            and self.trading_mode == "demo"
            and self.allow_order_submission
            and not self.allow_live_trading
        )
