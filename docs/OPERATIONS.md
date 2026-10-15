# Operations

## Read-only MetaApi diagnostic

This diagnostic checks the existing MetaApi account. It does not create, deploy, undeploy, or change the account, and it does not submit orders.

1. Install dependencies in a Python 3.11+ virtual environment.
2. Set `METAAPI_TOKEN` and `METAAPI_ACCOUNT_ID` in your local environment or deployment secret store.
3. Set `SYMBOL` to the exact symbol name shown by the connected broker terminal if it is not exactly `XAUUSD` or `GOLD`.
4. Run `python scripts/check_metaapi.py`.

The output intentionally avoids printing the API token, account ID, balance, or positions. A successful run confirms that the SDK synchronized and returned a quote; it does **not** prove that a strategy is profitable or authorize order execution.

Do not enable order submission. Strategy research, historical-data tests, risk controls, and demo execution validation are separate gates.
