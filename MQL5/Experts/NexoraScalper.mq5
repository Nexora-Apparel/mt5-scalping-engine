//+------------------------------------------------------------------+
//| NexoraScalper.mq5                                                |
//| Experimental, safety-gated MT5 Expert Advisor.                   |
//| Order submission is OFF by default. Demo testing only.            |
//+------------------------------------------------------------------+
#property strict
#property version   "1.000"
#property description "Experimental EMA-cross scalper with basic risk gates; disabled by default."


input bool   EnableDemoOrders       = false; // Keep false until Strategy Tester review
input bool   EmergencyStop          = true;  // True blocks all new entries
input double MinimumEquityUSD       = 10.0;  // Minimum account equity for entries; no EA-imposed upper balance limit
input double RiskPercentPerTrade    = 0.25;  // Normal profile: percent of current equity
input double MaxDailyLossPercent    = 1.00;  // Includes floating equity loss
input int    MaxSpreadPoints        = 80;    // Normal profile spread ceiling in broker points
input int    StopLossPoints         = 300;   // Normal profile stop in broker points
input int    TakeProfitPoints       = 450;   // Normal profile target in broker points
input bool   EnableSmallBalanceProfile = true; // Experimental profile for small-balance DEMO tests only
input double SmallBalanceThresholdUSD = 100.0; // Use small profile at/below this equity
input double SmallBalanceRiskPercent  = 0.5; // Conservative cap; may skip trades when minimum lot exceeds budget
input int    SmallBalanceMaxSpreadPoints = 20; // Strict spread ceiling for small-balance profile
input int    SmallBalanceStopLossPoints = 40; // Must cover stop level plus typical spread
input int    SmallBalanceTakeProfitPoints = 60; // Experimental 1.5:1 nominal target/risk
input int    FastEmaPeriod          = 9;
input int    SlowEmaPeriod          = 21;
input int    CooldownSeconds        = 60;
input ulong  MagicNumber            = 26101501;
input int    MaxDeviationPoints     = 20;

int fastHandle = INVALID_HANDLE;
int slowHandle = INVALID_HANDLE;
datetime lastBarTime = 0;
datetime lastEntryTime = 0;
string dayBaselineKey = "";
string lastEntryKey = "";
string dailyLossLockKey = "";
double testerDayStartBalance = 0.0;
datetime testerDayStartTime = 0;
bool testerDailyLossLocked = false;

bool IsDemoAccount()
{
   return AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO;
}

string BuildDayBaselineKey()
{
   string datePart = TimeToString(TimeCurrent(), TIME_DATE);
   StringReplace(datePart, ".", "");
   return StringFormat("NexoraBase_%I64d_%I64u_%s",
                       AccountInfoInteger(ACCOUNT_LOGIN), MagicNumber, datePart);
}

void RefreshDailyKeys()
{
   // Tester runs must not reuse terminal-global state from earlier tests.
   if(MQLInfoInteger(MQL_TESTER))
   {
      dayBaselineKey = "";
      lastEntryKey = "";
      dailyLossLockKey = "";
      return;
   }

   dayBaselineKey = BuildDayBaselineKey();
   dailyLossLockKey = StringFormat("NexoraLock_%I64d_%I64u_%s",
                                   AccountInfoInteger(ACCOUNT_LOGIN), MagicNumber,
                                   TimeToString(TimeCurrent(), TIME_DATE));
   StringReplace(dailyLossLockKey, ".", "");
   lastEntryKey = StringFormat("NexoraEntry_%I64d_%I64u",
                               AccountInfoInteger(ACCOUNT_LOGIN), MagicNumber);
   if(GlobalVariableCheck(lastEntryKey))
      lastEntryTime = (datetime)GlobalVariableGet(lastEntryKey);
}

double CalculateDayStartBalance()
{
   datetime now = TimeCurrent();
   MqlDateTime dayParts;
   if(!TimeToStruct(now, dayParts)) return 0.0;
   dayParts.hour = 0; dayParts.min = 0; dayParts.sec = 0;
   datetime dayStart = StructToTime(dayParts);
   if(!HistorySelect(dayStart, now))
   {
      Print("Nexora risk gate: cannot select today's account history.");
      return 0.0;
   }
   double netBalanceChanges = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      netBalanceChanges += HistoryDealGetDouble(ticket, DEAL_PROFIT);
      netBalanceChanges += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      netBalanceChanges += HistoryDealGetDouble(ticket, DEAL_SWAP);
      netBalanceChanges += HistoryDealGetDouble(ticket, DEAL_FEE);
   }
   double startBalance = AccountInfoDouble(ACCOUNT_BALANCE) - netBalanceChanges;
   if(startBalance <= 0.0) return 0.0;
   return startBalance;
}

double GetDayStartBalance()
{
   if(MQLInfoInteger(MQL_TESTER))
   {
      datetime now = TimeCurrent();
      MqlDateTime dayParts;
      if(!TimeToStruct(now, dayParts)) return 0.0;
      dayParts.hour = 0; dayParts.min = 0; dayParts.sec = 0;
      datetime currentDay = StructToTime(dayParts);
      if(testerDayStartTime != currentDay)
      {
         testerDayStartTime = currentDay;
         testerDailyLossLocked = false;
         testerDayStartBalance = CalculateDayStartBalance();
         if(testerDayStartBalance <= 0.0)
            testerDayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      }
      return testerDayStartBalance;
   }

   if(!GlobalVariableCheck(dayBaselineKey))
   {
      double baseline = CalculateDayStartBalance();
      if(baseline <= 0.0) return 0.0;
      if(!GlobalVariableSet(dayBaselineKey, baseline)) return 0.0;
   }
   return GlobalVariableGet(dayBaselineKey);
}

bool DailyLossLimitReached()
{
   // Refresh the date/baseline first so Strategy Tester can reset its latch at midnight.
   double startBalance = GetDayStartBalance();
   if(startBalance <= 0.0) return true;

   // Once breached, the daily limit stays latched until the next server day.
   // This prevents new entries if equity later recovers after a temporary drawdown.
   bool inTester = (bool)MQLInfoInteger(MQL_TESTER);
   if(inTester && testerDailyLossLocked) return true;
   if(!inTester && dailyLossLockKey != "" && GlobalVariableCheck(dailyLossLockKey))
      return true;
   double lossPercent = (startBalance - AccountInfoDouble(ACCOUNT_EQUITY))
                        / startBalance * 100.0;
   if(lossPercent >= MaxDailyLossPercent)
   {
      if(inTester)
         testerDailyLossLocked = true;
      else if(dailyLossLockKey != "")
         GlobalVariableSet(dailyLossLockKey, 1.0);
      return true;
   }
   return false;
}

bool HasPositionForSymbol()
{
   // Conservative: do not add a position if any position exists on this symbol.
   return PositionSelect(_Symbol);
}

bool IsNewBar()
{
   datetime barTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(barTime <= 0 || barTime == lastBarTime)
      return false;
   lastBarTime = barTime;
   return true;
}

bool IsSmallBalanceProfile()
{
   return EnableSmallBalanceProfile &&
          AccountInfoDouble(ACCOUNT_EQUITY) > 0.0 &&
          AccountInfoDouble(ACCOUNT_EQUITY) <= SmallBalanceThresholdUSD;
}

int EffectiveStopLossPoints()
{
   return IsSmallBalanceProfile() ? SmallBalanceStopLossPoints : StopLossPoints;
}

int EffectiveTakeProfitPoints()
{
   return IsSmallBalanceProfile() ? SmallBalanceTakeProfitPoints : TakeProfitPoints;
}

int EffectiveMaxSpreadPoints()
{
   return IsSmallBalanceProfile() ? SmallBalanceMaxSpreadPoints : MaxSpreadPoints;
}

double EffectiveRiskPercent()
{
   return IsSmallBalanceProfile() ? SmallBalanceRiskPercent : RiskPercentPerTrade;
}

bool SpreadIsAcceptable()
{
   long spread = 0;
   if(!SymbolInfoInteger(_Symbol, SYMBOL_SPREAD, spread))
      return false;
   return spread > 0 && spread <= EffectiveMaxSpreadPoints();
}

double CalculateVolume(double stopDistancePrice)
{
   // Use current equity so lot sizing automatically adapts as the account changes.
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney = equity * EffectiveRiskPercent() / 100.0;
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0.0)
      tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double volumeMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(riskMoney <= 0.0 || tickSize <= 0.0 || tickValue <= 0.0 ||
      stopDistancePrice <= 0.0 || volumeStep <= 0.0)
      return 0.0;

   double lossPerLot = (stopDistancePrice / tickSize) * tickValue;
   if(lossPerLot <= 0.0)
      return 0.0;

   double rawVolume = riskMoney / lossPerLot;
   // Round DOWN to the broker's volume step; never round risk upward.
   double volume = MathFloor(rawVolume / volumeStep) * volumeStep;
   volume = MathMin(volume, volumeMax);
   if(volume < volumeMin)
      return 0.0;

   int volumeDigits = 0;
   double step = volumeStep;
   while(volumeDigits < 8 && MathAbs(step - MathRound(step)) > 1e-8)
   {
      step *= 10.0;
      volumeDigits++;
   }
   return NormalizeDouble(volume, volumeDigits);
}

void LogSmallBalanceDiagnostics()
{
   if(!EnableSmallBalanceProfile || AccountInfoDouble(ACCOUNT_EQUITY) > SmallBalanceThresholdUSD)
      return;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double minVolume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskBudget = equity * SmallBalanceRiskPercent / 100.0;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double slDistance = EffectiveStopLossPoints() * point;
   double buyLoss = 0.0, sellLoss = 0.0, buyMargin = 0.0, sellMargin = 0.0;
   bool buyRiskOk = OrderCalcProfit(ORDER_TYPE_BUY, _Symbol, minVolume, ask, ask - slDistance, buyLoss);
   bool sellRiskOk = OrderCalcProfit(ORDER_TYPE_SELL, _Symbol, minVolume, bid, bid + slDistance, sellLoss);
   bool buyMarginOk = OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, minVolume, ask, buyMargin);
   bool sellMarginOk = OrderCalcMargin(ORDER_TYPE_SELL, _Symbol, minVolume, bid, sellMargin);

   Print("Nexora small-balance diagnostic: equity=", DoubleToString(equity, 2),
         " riskBudget=", DoubleToString(riskBudget, 2),
         " minVolume=", DoubleToString(minVolume, 2),
         " point=", DoubleToString(point, 5),
         " spreadPoints=", (long)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD),
         " stopsLevel=", (long)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
         " SLpoints=", EffectiveStopLossPoints(),
         " TPpoints=", EffectiveTakeProfitPoints());
   Print("Nexora small-balance diagnostic: buyRiskOK=", buyRiskOk,
         " buyStopLoss=", buyRiskOk ? DoubleToString(-buyLoss, 2) : "n/a",
         " buyMarginOK=", buyMarginOk,
         " buyMargin=", buyMarginOk ? DoubleToString(buyMargin, 2) : "n/a",
         " sellRiskOK=", sellRiskOk,
         " sellStopLoss=", sellRiskOk ? DoubleToString(-sellLoss, 2) : "n/a",
         " sellMarginOK=", sellMarginOk,
         " sellMargin=", sellMarginOk ? DoubleToString(sellMargin, 2) : "n/a",
         " note=diagnostic only; no order sent");
}

bool GetCrossSignal(bool &buySignal, bool &sellSignal)
{
   buySignal = false;
   sellSignal = false;

   double fast[2], slow[2];
   // Copy bars 2 and 1 (closed bars); element 0 is older, element 1 newer.
   if(CopyBuffer(fastHandle, 0, 1, 2, fast) != 2 ||
      CopyBuffer(slowHandle, 0, 1, 2, slow) != 2)
      return false;

   buySignal  = (fast[0] <= slow[0] && fast[1] > slow[1]);
   sellSignal = (fast[0] >= slow[0] && fast[1] < slow[1]);
   return true;
}

bool SafetyGatesPass()
{
   if(!EnableDemoOrders || EmergencyStop)
      return false;
   bool inTester = (bool)MQLInfoInteger(MQL_TESTER);
   if(!inTester && !IsDemoAccount())
      return false;
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
      return false;
   // No configured maximum account balance: sizing remains percentage-based,
   // while broker volume/margin limits still apply.
   if(MinimumEquityUSD <= 0.0 || AccountInfoDouble(ACCOUNT_EQUITY) < MinimumEquityUSD)
      return false;
   if(!inTester && (!TerminalInfoInteger(TERMINAL_CONNECTED) ||
                    !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)))
      return false;
   if(RiskPercentPerTrade <= 0.0 || RiskPercentPerTrade > 0.5 ||
      MaxDailyLossPercent <= 0.0 || MaxDailyLossPercent > 2.0)
      return false;
   if(EnableSmallBalanceProfile &&
      (SmallBalanceThresholdUSD <= 0.0 || SmallBalanceRiskPercent <= 0.0 ||
       SmallBalanceRiskPercent > 0.5 || SmallBalanceMaxSpreadPoints <= 0 ||
       SmallBalanceStopLossPoints <= 0 ||
       SmallBalanceTakeProfitPoints <= 0))
      return false;
   if(StopLossPoints <= 0 || TakeProfitPoints <= 0 ||
      FastEmaPeriod <= 0 || SlowEmaPeriod <= FastEmaPeriod)
      return false;
   if(DailyLossLimitReached() || !SpreadIsAcceptable() || HasPositionForSymbol())
      return false;
   if(CooldownSeconds < 0 || MaxSpreadPoints <= 0 || MaxDeviationPoints < 0)
      return false;
   if(lastEntryTime > 0 && TimeCurrent() - lastEntryTime < CooldownSeconds)
      return false;
   return true;
}

void TryEntry()
{
   bool buySignal = false, sellSignal = false;
   if(!GetCrossSignal(buySignal, sellSignal))
      return;
   if(!buySignal && !sellSignal)
      return;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   long stopsLevel = 0;
   SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL, stopsLevel);
   int slPoints = EffectiveStopLossPoints();
   int tpPoints = EffectiveTakeProfitPoints();
   long spreadPoints = 0;
   if(!SymbolInfoInteger(_Symbol, SYMBOL_SPREAD, spreadPoints))
      return;
   // For market execution, the stop must also clear the broker's stop level
   // from the opposite quote (bid/ask), so account for the current spread.
   if(point <= 0.0 || slPoints < stopsLevel + spreadPoints ||
      tpPoints < stopsLevel + spreadPoints)
      return;

   double stopDistance = slPoints * point;
   double volume = CalculateVolume(stopDistance);
   if(volume <= 0.0)
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;

   double sl = 0.0, tp = 0.0;
   double entryPrice = buySignal ? tick.ask : tick.bid;
   if(buySignal)
   {
      sl = NormalizeDouble(tick.ask - stopDistance, digits);
      tp = NormalizeDouble(tick.ask + tpPoints * point, digits);
   }
   else
   {
      sl = NormalizeDouble(tick.bid + stopDistance, digits);
      tp = NormalizeDouble(tick.bid - tpPoints * point, digits);
   }

   // Verify the broker-calculated loss for the chosen volume; never force the
   // minimum lot if it would exceed the configured per-trade risk budget.
   double estimatedStopProfit = 0.0;
   ENUM_ORDER_TYPE intendedType = buySignal ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcProfit(intendedType, _Symbol, volume, entryPrice, sl, estimatedStopProfit))
   {
      Print("Nexora entry blocked: unable to calculate stop-loss risk.");
      return;
   }
   double riskBudget = AccountInfoDouble(ACCOUNT_EQUITY) * EffectiveRiskPercent() / 100.0;
   if(estimatedStopProfit >= 0.0 || -estimatedStopProfit > riskBudget + 0.000001)
   {
      Print("Nexora entry blocked: minimum/rounded volume exceeds risk budget. Estimated loss=",
            DoubleToString(-estimatedStopProfit, 2), " budget=", DoubleToString(riskBudget, 2));
      return;
   }

   // Native MQL5 request API avoids a dependency on the standard Trade.mqh library.
   long fillingFlags = 0;
   long executionMode = 0;
   if(!SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE, fillingFlags) ||
      !SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE, executionMode))
      return;

   ENUM_ORDER_TYPE_FILLING fillingMode;
   if((fillingFlags & SYMBOL_FILLING_FOK) != 0)
      fillingMode = ORDER_FILLING_FOK;
   else if((fillingFlags & SYMBOL_FILLING_IOC) != 0)
      fillingMode = ORDER_FILLING_IOC;
   else if(executionMode != SYMBOL_TRADE_EXECUTION_MARKET)
      fillingMode = ORDER_FILLING_RETURN;
   else
   {
      Print("Nexora entry blocked: broker reports no compatible filling mode.");
      return;
   }

   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   request.action       = TRADE_ACTION_DEAL;
   request.symbol       = _Symbol;
   request.volume       = volume;
   request.type         = buySignal ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   request.price        = buySignal ? tick.ask : tick.bid;
   request.sl           = sl;
   request.tp           = tp;
   request.deviation    = (ulong)MaxDeviationPoints;
   request.magic        = MagicNumber;
   request.comment      = "Nexora EMA cross demo";
   request.type_time    = ORDER_TIME_GTC;
   request.type_filling = fillingMode;

   MqlTradeCheckResult check = {};
   if(!OrderCheck(request, check))
   {
      Print("Nexora entry blocked by OrderCheck; error=", GetLastError());
      return;
   }
   if(check.retcode != TRADE_RETCODE_DONE)
   {
      Print("Nexora entry blocked by preflight check; retcode=", check.retcode,
            " description=", check.comment);
      return;
   }

   bool sent = OrderSend(request, result);
   if(sent && (result.retcode == TRADE_RETCODE_DONE ||
               result.retcode == TRADE_RETCODE_PLACED ||
               result.retcode == TRADE_RETCODE_DONE_PARTIAL))
   {
      lastEntryTime = TimeCurrent();
      if(lastEntryKey != "")
         GlobalVariableSet(lastEntryKey, (double)lastEntryTime);
   }
   else
      Print("Nexora entry rejected; retcode=", result.retcode,
            " description=", result.comment);
}

int OnInit()
{
   if(MinimumEquityUSD <= 0.0 || FastEmaPeriod <= 0 || SlowEmaPeriod <= FastEmaPeriod ||
      RiskPercentPerTrade <= 0.0 || MaxDailyLossPercent <= 0.0 ||
      StopLossPoints <= 0 || TakeProfitPoints <= 0)
      return INIT_PARAMETERS_INCORRECT;

   fastHandle = iMA(_Symbol, PERIOD_CURRENT, FastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   slowHandle = iMA(_Symbol, PERIOD_CURRENT, SlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(fastHandle == INVALID_HANDLE || slowHandle == INVALID_HANDLE)
      return INIT_FAILED;

   RefreshDailyKeys();
   GetDayStartBalance(); // Persist baseline across terminal restarts for this account/day.
   lastBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);

   Print("NexoraScalper initialized. EnableDemoOrders=", EnableDemoOrders,
         ", EmergencyStop=", EmergencyStop,
         ", SmallBalanceProfile=", EnableSmallBalanceProfile,
         ", SmallBalanceRiskPercent=", SmallBalanceRiskPercent,
         ". Experimental only; live trading is blocked by design.");
   LogSmallBalanceDiagnostics();
   return INIT_SUCCEEDED;
}

void OnTick()
{
   // Refresh the date-keyed baseline at midnight, including after a terminal restart.
   RefreshDailyKeys();
   if(!IsNewBar())
      return;
   if(!SafetyGatesPass())
      return;
   TryEntry();
}

void OnDeinit(const int reason)
{
   if(fastHandle != INVALID_HANDLE)
      IndicatorRelease(fastHandle);
   if(slowHandle != INVALID_HANDLE)
      IndicatorRelease(slowHandle);
}
