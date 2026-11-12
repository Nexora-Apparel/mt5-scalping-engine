//+------------------------------------------------------------------+
//| VeltrixDemoDiagnostics.mq5                                       |
//| Read-only Exness DEMO account and quote verification.            |
//| No trade, position, order, or deal APIs are used.                 |
//+------------------------------------------------------------------+
#property strict
#property version   "1.000"
#property description "VELTRIX read-only DEMO account and XAUUSD/XAGUSD quote diagnostic."

input long   ExpectedDemoLogin = 0;
input string ExpectedDemoServer = "";
input ulong  QuoteMaxAgeMilliseconds = 15000;
input double MaxSpreadPoints = 1000.0;
input int    StableSamplesRequired = 5;
input int    DiagnosticTimeoutSeconds = 90;

string g_symbols[2] = {"XAUUSD", "XAGUSD"};
int g_stable_samples = 0;
ulong g_started_ms = 0;
bool g_finished = false;

bool VerifyAccount(string &reason)
{
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
   {
      reason = "terminal is disconnected";
      return false;
   }

   long login = (long)AccountInfoInteger(ACCOUNT_LOGIN);
   long mode = (long)AccountInfoInteger(ACCOUNT_TRADE_MODE);
   string server = AccountInfoString(ACCOUNT_SERVER);

   if(login != ExpectedDemoLogin)
   {
      reason = "connected account login does not match configured login";
      return false;
   }
   if(mode != ACCOUNT_TRADE_MODE_DEMO)
   {
      reason = "ACCOUNT_TRADE_MODE is not DEMO";
      return false;
   }
   if(server != ExpectedDemoServer)
   {
      reason = "connected server does not exactly match configured server";
      return false;
   }

   reason = "";
   return true;
}

bool VerifyQuote(const string symbol, string &reason, double &bid,
                 double &ask, double &spread_points, long &age_ms)
{
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
   {
      reason = symbol + " has no readable tick";
      return false;
   }

   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(point <= 0.0 || tick.bid <= 0.0 || tick.ask <= tick.bid)
   {
      reason = symbol + " has invalid point, bid, or ask";
      return false;
   }

   long now_ms = (long)TimeGMT() * 1000;
   if(now_ms <= 0 || tick.time_msc <= 0)
   {
      reason = symbol + " has no valid quote timestamp";
      return false;
   }

   age_ms = now_ms - tick.time_msc;
   if(age_ms < -5000 || age_ms > (long)QuoteMaxAgeMilliseconds)
   {
      reason = StringFormat("%s quote is stale or timestamp is invalid (age_ms=%I64d)",
                            symbol, age_ms);
      return false;
   }

   bid = tick.bid;
   ask = tick.ask;
   spread_points = (ask - bid) / point;
   if(spread_points <= 0.0 || spread_points > MaxSpreadPoints)
   {
      reason = StringFormat("%s spread outside configured limit (spread_points=%.2f)",
                            symbol, spread_points);
      return false;
   }

   reason = "";
   return true;
}

void StopWithFailure(const string reason)
{
   if(g_finished)
      return;
   g_finished = true;
   Print("VELTRIX DEMO DIAGNOSTIC FAILED | ", reason);
   EventKillTimer();
   ExpertRemove();
}

int OnInit()
{
   if(ExpectedDemoLogin <= 0 || ExpectedDemoServer == "")
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | expected demo login/server missing");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(QuoteMaxAgeMilliseconds < 1000 || QuoteMaxAgeMilliseconds > 60000 ||
      MaxSpreadPoints <= 0.0 || MaxSpreadPoints > 10000.0 ||
      StableSamplesRequired < 2 || StableSamplesRequired > 30 ||
      DiagnosticTimeoutSeconds < 15 || DiagnosticTimeoutSeconds > 300)
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | diagnostic input outside safe bounds");
      return INIT_PARAMETERS_INCORRECT;
   }

   bool connected = false;
   for(int attempt = 0; attempt < 90; attempt++)
   {
      if(TerminalInfoInteger(TERMINAL_CONNECTED))
      {
         connected = true;
         break;
      }
      if(IsStopped())
         return INIT_FAILED;
      if(attempt == 0 || (attempt + 1) % 15 == 0)
         PrintFormat("VELTRIX DEMO DIAGNOSTIC WAIT | broker connection attempt=%d/90",
                     attempt + 1);
      Sleep(1000);
   }

   if(!connected)
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | broker connection timeout");
      return INIT_FAILED;
   }

   string reason;
   if(!VerifyAccount(reason))
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | ", reason);
      return INIT_FAILED;
   }

   for(int i = 0; i < 2; i++)
   {
      if(!SymbolSelect(g_symbols[i], true))
      {
         Print("VELTRIX DEMO DIAGNOSTIC FAILED | could not select exact symbol ",
               g_symbols[i]);
         return INIT_FAILED;
      }
   }

   g_started_ms = GetTickCount64();
   if(!EventSetTimer(1))
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | timer initialization failed");
      return INIT_FAILED;
   }

   Print("VELTRIX DEMO DIAGNOSTIC STARTED | account mode, login, server, and both metal quotes will be checked; trading disabled");
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   if(g_finished)
      return;

   string reason;
   if(!VerifyAccount(reason))
   {
      StopWithFailure(reason);
      return;
   }

   bool all_quotes_valid = true;
   for(int i = 0; i < 2; i++)
   {
      double bid = 0.0;
      double ask = 0.0;
      double spread = 0.0;
      long age_ms = -1;
      if(!VerifyQuote(g_symbols[i], reason, bid, ask, spread, age_ms))
      {
         all_quotes_valid = false;
         Print("VELTRIX QUOTE BLOCKED | ", reason);
         break;
      }

      PrintFormat("VELTRIX QUOTE OK | symbol=%s bid=%.*f ask=%.*f spread_points=%.2f age_ms=%I64d",
                  g_symbols[i],
                  (int)SymbolInfoInteger(g_symbols[i], SYMBOL_DIGITS), bid,
                  (int)SymbolInfoInteger(g_symbols[i], SYMBOL_DIGITS), ask,
                  spread, age_ms);
   }

   if(all_quotes_valid)
      g_stable_samples++;
   else
      g_stable_samples = 0;

   if(g_stable_samples >= StableSamplesRequired)
   {
      g_finished = true;
      PrintFormat("VELTRIX DEMO DIAGNOSTIC PASSED | mode=DEMO login_match=true server_match=true terminal_connected=true symbols=XAUUSD,XAGUSD stable_samples=%d trading=disabled",
                  g_stable_samples);
      EventKillTimer();
      ExpertRemove();
      return;
   }

   ulong elapsed_ms = GetTickCount64() - g_started_ms;
   if(elapsed_ms >= (ulong)DiagnosticTimeoutSeconds * 1000)
      StopWithFailure("both XAUUSD and XAGUSD did not produce enough consecutive fresh, valid quotes before timeout");
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("VELTRIX DEMO DIAGNOSTIC STOPPED | no trading operations were available");
}
