//+------------------------------------------------------------------+
//| VeltrixScalper.mq5                                               |
//| Replacement EA foundation: read-only market health only.        |
//| Trading is intentionally not implemented or permitted here.     |
//+------------------------------------------------------------------+
#property strict
#property version   "1.000"
#property description "VELTRIX scalper foundation; market health only, no order submission."

#include "..\\Include\\Veltrix\\MarketGuard.mqh"
#include "..\\Include\\Veltrix\\RiskAllocator.mqh"
#include "..\\Include\\Veltrix\\PositionRegistry.mqh"
#include "..\\Include\\Veltrix\\ExecutionGuard.mqh"
#include "..\\Include\\Veltrix\\BrokerReconciler.mqh"
#include "..\\Include\\Veltrix\\ExecutionCoordinator.mqh"
#include "..\\Include\\Veltrix\\StrategyResearch.mqh"
#include "..\\Include\\Veltrix\\FeatureCollector.mqh"
#include "..\\Include\\Veltrix\\FeatureDatasetExporter.mqh"

input ulong  MaxQuoteAgeMilliseconds = 2500;
input double MaxSpreadPoints        = 50.0;
input uint   HealthPollMilliseconds = 250;

CVxMarketGuard g_market;
bool g_last_health_state=false;
string g_last_health_reason="";

int OnInit()
{
   if(!g_market.Init(_Symbol,MaxQuoteAgeMilliseconds,MaxSpreadPoints))
   {
      Print("VELTRIX INIT FAILED: market guard could not initialize for ",_Symbol);
      return INIT_FAILED;
   }

   VxSymbolSpec spec;
   string reason;
   if(!g_market.ReadSymbolSpec(spec,reason))
   {
      Print("VELTRIX INIT FAILED: ",reason);
      return INIT_FAILED;
   }

   PrintFormat("VELTRIX READ-ONLY FOUNDATION | symbol=%s point=%g tick_size=%g tick_value_loss=%g volume_min=%g volume_step=%g stops=%I64d freeze=%I64d trade_mode=%I64d execution=%I64d filling=%I64d",
               spec.symbol,spec.point,spec.tick_size,spec.tick_value_loss,
               spec.volume_min,spec.volume_step,spec.stops_level_points,
               spec.freeze_level_points,spec.trade_mode,spec.execution_mode,
               spec.filling_mode);

   uint poll=HealthPollMilliseconds;
   if(poll<100) poll=100;
   if(!EventSetMillisecondTimer(poll))
   {
      Print("VELTRIX INIT FAILED: millisecond timer could not be started");
      return INIT_FAILED;
   }

   Print("VELTRIX SAFE MODE: market health, read-only reconciliation, and state-only execution coordination. No order APIs are called.");
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   VxQuoteSnapshot quote;
   string reason;
   bool healthy=g_market.ReadQuote(quote,reason);

   if(healthy!=g_last_health_state || (!healthy && reason!=g_last_health_reason))
   {
      if(healthy)
         PrintFormat("VELTRIX MARKET HEALTH OK | symbol=%s bid=%.*f ask=%.*f spread=%.2f points broker_age=%dms unchanged_age=%I64ums",
                     _Symbol,(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS),
                     quote.tick.bid,(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS),
                     quote.tick.ask,quote.spread_points,
                     quote.broker_quote_age_ms,quote.local_unchanged_age_ms);
      else
         Print("VELTRIX MARKET HEALTH BLOCKED | ",_Symbol," | ",reason);

      g_last_health_state=healthy;
      g_last_health_reason=reason;
   }
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("VELTRIX read-only foundation stopped. No trading actions were available.");
}
