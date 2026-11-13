//+------------------------------------------------------------------+
//| VeltrixDemoDiagnostics.mq5                                       |
//| Read-only Exness DEMO and XAUUSD contract/quote verification.    |
//| No trade, position, order, or deal APIs are used.                 |
//+------------------------------------------------------------------+
#property strict
#property version   "1.100"
#property description "VELTRIX read-only DEMO account and XAUUSD-only quote diagnostic."

input long   ExpectedDemoLogin = 0;
input string ExpectedDemoServer = "";
input ulong  QuoteMaxAgeMilliseconds = 15000;
input double MaxSpreadPoints = 1000.0;
input int    StableSamplesRequired = 5;
input int    DiagnosticTimeoutSeconds = 90;

string g_symbol = "";
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
   if(TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
   {
      reason = "terminal trading permission is enabled";
      return false;
   }
   if(TerminalInfoInteger(TERMINAL_DLLS_ALLOWED))
   {
      reason = "terminal DLL imports are enabled";
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

bool ResolveXauUsdSymbol(string &resolved,string &reason)
{
   string candidates[];
   int total=SymbolsTotal(false);
   for(int i=0;i<total;i++)
   {
      string name=SymbolName(i,false);
      string upper=name;
      StringToUpper(upper);
      if(StringLen(upper)<6 || StringSubstr(upper,0,6)!="XAUUSD")
         continue;

      string base=SymbolInfoString(name,SYMBOL_CURRENCY_BASE);
      string profit=SymbolInfoString(name,SYMBOL_CURRENCY_PROFIT);
      if(base!="XAU" || profit!="USD")
         continue;

      int n=ArraySize(candidates);
      ArrayResize(candidates,n+1);
      candidates[n]=name;
   }

   int count=ArraySize(candidates);
   if(count<=0)
   {
      reason="no broker symbol with XAUUSD prefix and XAU/USD contract metadata";
      return false;
   }

   resolved="";
   for(int i=0;i<count;i++)
      if(candidates[i]=="XAUUSD") { resolved="XAUUSD"; break; }

   if(resolved=="")
   {
      if(count!=1)
      {
         reason=StringFormat("ambiguous XAUUSD broker contracts: %d metadata-valid candidates",count);
         return false;
      }
      resolved=candidates[0];
   }

   if(!SymbolSelect(resolved,true))
   {
      reason="verified XAUUSD broker contract could not be selected";
      resolved="";
      return false;
   }
   reason="";
   return true;
}

bool VerifyQuote(string &reason,double &bid,double &ask,
                 double &spread_points,long &age_ms)
{
   if(g_symbol=="")
   {
      reason="verified XAUUSD broker symbol is unavailable";
      return false;
   }

   MqlTick tick;
   if(!SymbolInfoTick(g_symbol,tick))
   {
      reason="XAUUSD has no readable tick";
      return false;
   }

   double point=SymbolInfoDouble(g_symbol,SYMBOL_POINT);
   if(point<=0.0 || tick.bid<=0.0 || tick.ask<=tick.bid)
   {
      reason="XAUUSD has invalid point, bid, or ask";
      return false;
   }

   long now_ms=(long)TimeGMT()*1000;
   if(now_ms<=0 || tick.time_msc<=0)
   {
      reason="XAUUSD has no valid quote timestamp";
      return false;
   }

   age_ms=now_ms-tick.time_msc;
   if(age_ms < -5000 || age_ms>(long)QuoteMaxAgeMilliseconds)
   {
      reason=StringFormat("XAUUSD quote is stale or timestamp is invalid (age_ms=%I64d)",age_ms);
      return false;
   }

   bid=tick.bid;
   ask=tick.ask;
   spread_points=(ask-bid)/point;
   if(spread_points<=0.0 || spread_points>MaxSpreadPoints)
   {
      reason=StringFormat("XAUUSD spread outside configured limit (spread_points=%.2f)",spread_points);
      return false;
   }
   reason="";
   return true;
}

void StopWithFailure(const string reason)
{
   if(g_finished) return;
   g_finished=true;
   Print("VELTRIX DEMO DIAGNOSTIC FAILED | ",reason);
   EventKillTimer();
   ExpertRemove();
}

int OnInit()
{
   if(ExpectedDemoLogin<=0 || ExpectedDemoServer=="")
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | expected demo login/server missing");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(QuoteMaxAgeMilliseconds<1000 || QuoteMaxAgeMilliseconds>60000 ||
      MaxSpreadPoints<=0.0 || MaxSpreadPoints>10000.0 ||
      StableSamplesRequired<2 || StableSamplesRequired>30 ||
      DiagnosticTimeoutSeconds<15 || DiagnosticTimeoutSeconds>300)
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | diagnostic input outside safe bounds");
      return INIT_PARAMETERS_INCORRECT;
   }

   bool connected=false;
   for(int attempt=0;attempt<90;attempt++)
   {
      if(TerminalInfoInteger(TERMINAL_CONNECTED)) { connected=true; break; }
      if(IsStopped()) return INIT_FAILED;
      if(attempt==0 || (attempt+1)%15==0)
         PrintFormat("VELTRIX DEMO DIAGNOSTIC WAIT | broker connection attempt=%d/90",attempt+1);
      Sleep(1000);
   }
   if(!connected)
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | broker connection timeout");
      return INIT_FAILED;
   }

   string reason="";
   if(!VerifyAccount(reason))
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | ",reason);
      return INIT_FAILED;
   }
   if(!ResolveXauUsdSymbol(g_symbol,reason))
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | ",reason);
      return INIT_FAILED;
   }

   g_started_ms=GetTickCount64();
   if(!EventSetTimer(1))
   {
      Print("VELTRIX DEMO DIAGNOSTIC FAILED | timer initialization failed");
      return INIT_FAILED;
   }
   Print("VELTRIX DEMO DIAGNOSTIC STARTED | DEMO identity and XAUUSD-only contract/quote checks; trading disabled");
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   if(g_finished) return;
   string reason="";
   if(!VerifyAccount(reason)) { StopWithFailure(reason); return; }

   double bid=0.0,ask=0.0,spread=0.0;
   long age_ms=-1;
   if(VerifyQuote(reason,bid,ask,spread,age_ms))
   {
      g_stable_samples++;
      PrintFormat("VELTRIX QUOTE OK | symbol=XAUUSD broker_symbol=%s bid=%.*f ask=%.*f spread_points=%.2f age_ms=%I64d",
                  g_symbol,(int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS),bid,
                  (int)SymbolInfoInteger(g_symbol,SYMBOL_DIGITS),ask,spread,age_ms);
   }
   else
   {
      g_stable_samples=0;
      Print("VELTRIX QUOTE BLOCKED | ",reason);
   }

   if(g_stable_samples>=StableSamplesRequired)
   {
      g_finished=true;
      PrintFormat("VELTRIX DEMO DIAGNOSTIC PASSED | mode=DEMO login_match=true server_match=true terminal_connected=true symbol=XAUUSD trading=disabled stable_samples=%d",
                  g_stable_samples);
      EventKillTimer();
      ExpertRemove();
      return;
   }

   if(GetTickCount64()-g_started_ms >= (ulong)DiagnosticTimeoutSeconds*1000)
      StopWithFailure("XAUUSD did not produce enough consecutive fresh, valid quotes before timeout");
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("VELTRIX DEMO DIAGNOSTIC STOPPED | no trading operations were available");
}
