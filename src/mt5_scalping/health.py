"""Read-only health result model. This module never submits orders."""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class HealthResult:
    checked_at: datetime
    credentials_configured: bool
    account_id_configured: bool
    connection_state: str
    quote_state: str
    details: str

    @classmethod
    def not_checked(cls, credentials_configured: bool, account_id_configured: bool) -> "HealthResult":
        return cls(
            checked_at=datetime.now(timezone.utc),
            credentials_configured=credentials_configured,
            account_id_configured=account_id_configured,
            connection_state="not_checked",
            quote_state="not_checked",
            details="No MetaApi network check has been run. No orders were submitted.",
        )
