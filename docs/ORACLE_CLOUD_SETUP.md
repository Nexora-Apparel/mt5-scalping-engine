# Experimental no-cost cloud route for MT5

This route is intended for a user who only has an Android phone and cannot pay for a VPS. It is **not yet validated on Oracle Cloud**, and a free instance is not guaranteed to be available or reliable.

## Important constraints

- MT5 desktop Expert Advisors cannot run inside the Android MT5 app. The desktop terminal must run on a computer or remote server.
- The bootstrap script supports **x86_64/AMD Linux only**. Do not use Oracle Ampere A1/ARM for this script.
- Oracle's Always Free AMD VM.Standard.E2.1.Micro has 1 GB RAM. The script adds a 2 GB swap file on a small VM, but Wine + MT5 may still be slow or fail under memory pressure.
- Oracle can report "out of host capacity" in a region. Always Free compute can also be reclaimed under Oracle's idle-instance policy. This is a test route, not guaranteed uptime.
- Oracle sign-up typically requires a credit/debit card that functions like a credit card. Oracle says the card is not charged unless the account is upgraded; do **not** upgrade or create paid resources. Virtual, prepaid, and PIN-only debit cards are not accepted by Oracle's stated policy.
- The EA stays fail-closed: `EnableDemoOrders=false` and `EmergencyStop=true`. The bootstrap does not configure a trading account or place orders.

## 1. Create an Always Free VM

1. Open the official [Oracle Cloud Free Tier page](https://www.oracle.com/cloud/free/).
2. Create one account only; do not attempt duplicate free accounts.
3. Choose a home region you can use. Always Free compute capacity varies by region.
4. Create an **Always Free** x86_64 Ubuntu instance using `VM.Standard.E2.1.Micro` (AMD, 1 GB RAM). Do not select Ampere A1/ARM for this setup.
5. Add an SSH public key. Keep the private key on your phone and never upload it to this repository.
6. Use only the free shape and storage limits. Do not enable paid upgrades or paid resources.

Official Oracle references: [Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) and [Free Tier FAQ](https://www.oracle.com/cloud/free/faq/).

## 2. Run the bootstrap from the VM

Connect to the VM over SSH from your phone or Oracle's browser-based console, then run:

```bash
git clone https://github.com/Nexora-Apparel/mt5-scalping-engine.git
cd mt5-scalping-engine
chmod +x scripts/bootstrap_mt5_linux.sh
./scripts/bootstrap_mt5_linux.sh
```

The script installs Wine and Xvfb, creates a swap file if the VM has under 2 GB RAM and no swap, downloads the official MetaTrader installer, waits for the desktop terminal files, places the current EA source in the portable terminal folder, and compiles it. Logs are saved to `~/mt5-setup-logs/`.

The script may take several minutes. It is experimental and has not yet been executed on an Oracle VM. If it fails, preserve the logs and stop rather than switching to a paid instance.

MetaQuotes documents MT5 on Linux through Wine here: [MetaTrader 5 on Linux](https://www.mql5.com/en/articles/625). MT5 startup configuration can load an EA and chart from an INI file; see [Automating Terminal Startup](https://www.mql5.com/en/articles/20147).

## 3. What remains after bootstrap

The bootstrap intentionally stops before account login or trading. The remaining steps are:

1. Configure a **demo account only**, using credentials entered privately on the VM. Never put credentials in GitHub, source code, logs, or this chat.
2. Confirm the terminal connects and downloads history for the intended broker symbol.
3. Run Strategy Tester with a defined date range, realistic spread/commission, and a report saved to the VM.
4. Review drawdown, trade count, profit factor, expectancy, slippage sensitivity, and out-of-sample performance.
5. Only after the backtest is reviewed, perform demo forward testing. The EA's default order-submission switch and emergency stop must remain closed until that explicit demo test is ready.

## Security notes

- Do not open VNC/RDP ports to the public internet for this setup.
- Do not store broker passwords in a public repository or paste them into ChatGPT.
- Do not enable real/live trading. Compilation only proves the source compiles; it does not establish profitability or safety.
- If Oracle account verification requires a payment card you do not have, stop here. Do not pay for MetaApi or a VPS just to continue this experiment.
