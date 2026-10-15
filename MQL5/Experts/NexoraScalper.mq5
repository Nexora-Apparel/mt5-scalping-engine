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
input double RiskPercentPerTrade    = 0.25;  // Percent of reconstructed start-of-day balance
input double MaxDailyLossPercent    = 1.00;  // Includes floating equity loss
input int    MaxSpreadPoints        = 80;    // Broker points; tune per symbol after measuring
input int    StopLossPoints         = 300;   // Must be calibrated per symbol/broker
input int    TakeProfitPoints       = 450;   // Must be calibrated per symbol/broker
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
double testerDayStartBalance = 0.0;
datetime testerDayStartTime = 0;

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
      return;
   }

   dayBaselineKey = BuildDayBaselineKey();
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
   double startBalance = GetDayStartBalance();
   if(startBalance <= 0.0) return true;
   double lossPercent = (startBalance - AccountInfoDouble(ACCOUNT_EQUITY))
                        / startBalance * 100.0;
   return lossPercent >= MaxDailyLossPercent;
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

bool SpreadIsAcceptable()
{
   long spread = 0;
   if(!SymbolInfoInteger(_Symbol, SYMBOL_SPREAD, spread))
      return false;
   return spread > 0 && spread <= MaxSpreadPoints;
}

double CalculateVolume(double stopDistancePrice)
{
   double equity = GetDayStartBalance();
   double riskMoney = equity * RiskPercentPerTrade / 100.0;
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
   if(!inTester && (!TerminalInfoInteger(TERMINAL_CONNECTED) ||
                    !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)))
      return false;
   if(RiskPercentPerTrade <= 0.0 || RiskPercentPerTrade > 0.5 ||
      MaxDailyLossPercent <= 0.0 || MaxDailyLossPercent > 2.0)
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
   if(point <= 0.0 || StopLossPoints < stopsLevel || TakeProfitPoints < stopsLevel)
      return;

   double stopDistance = StopLossPoints * point;
   double volume = CalculateVolume(stopDistance);
   if(volume <= 0.0)
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;

   double sl = 0.0, tp = 0.0;
   if(buySignal)
   {
      sl = NormalizeDouble(tick.ask - stopDistance, digits);
      tp = NormalizeDouble(tick.ask + TakeProfitPoints * point, digits);
   }
   else
   {
      sl = NormalizeDouble(tick.bid + stopDistance, digits);
      tp = NormalizeDouble(tick.bid - TakeProfitPoints * point, digits);
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
   if(FastEmaPeriod <= 0 || SlowEmaPeriod <= FastEmaPeriod ||
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
         ". This is experimental and not approved for live trading.");
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
