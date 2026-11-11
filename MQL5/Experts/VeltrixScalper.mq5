//+------------------------------------------------------------------+
//| VeltrixScalper.mq5                                               |
//| Replacement EA foundation: read-only market health only.        |
//| Trading is intentionally not implemented or permitted here.     |
//+------------------------------------------------------------------+
#property strict
#property version   "1.000"
#property description "VELTRIX safe foundation; optional research data collection only, no order submission."

#include "..\\Include\\Veltrix\\MarketGuard.mqh"
#include "..\\Include\\Veltrix\\RiskAllocator.mqh"
#include "..\\Include\\Veltrix\\PositionRegistry.mqh"
#include "..\\Include\\Veltrix\\ExecutionGuard.mqh"
#include "..\\Include\\Veltrix\\BrokerReconciler.mqh"
#include "..\\Include\\Veltrix\\ExecutionCoordinator.mqh"
#include "..\\Include\\Veltrix\\StrategyResearch.mqh"
#include "..\\Include\\Veltrix\\FeatureCollector.mqh"
#include "..\\Include\\Veltrix\\FeatureDatasetExporter.mqh"
#include "..\\Include\\Veltrix\\FeaturePipeline.mqh"

input ulong  MaxQuoteAgeMilliseconds = 2500;
input double MaxSpreadPoints        = 50.0;
input uint   HealthPollMilliseconds = 250;
input bool   EnableDatasetCollection = false;
input uint   FeatureLookbackSeconds = 60;
input int    FeatureMinObservations = 10;
input int    FeatureBufferCapacity = 10000;
input string DatasetSourceId = "";
input long   ExpectedDemoLogin = 0;
input string ExpectedDemoServer = "";

CVxMarketGuard g_market;
CVxFeaturePipeline g_feature_pipeline;
bool g_dataset_fault_reported=false;
bool g_last_health_state=false;
string g_last_health_reason="";

int OnInit()
{
   if(EnableDatasetCollection)
   {
      bool expected_account=(ExpectedDemoLogin>0 &&
                             ExpectedDemoServer!="" &&
                             TerminalInfoInteger(TERMINAL_CONNECTED) &&
                             AccountInfoInteger(ACCOUNT_LOGIN)==ExpectedDemoLogin &&
                             AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO &&
                             AccountInfoString(ACCOUNT_SERVER)==ExpectedDemoServer);
      if(!expected_account)
      {
         Print("DATASET DEMO ACCOUNT GUARD FAILED: collection requires the exact connected DEMO account and configured server");
         return INIT_FAILED;
      }
      Print("DATASET DEMO ACCOUNT GUARD PASSED: exact configured DEMO account verified; automated trading disabled");
   }
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

   if(EnableDatasetCollection)
   {
      if(FeatureLookbackSeconds<1 || FeatureLookbackSeconds>600)
      {
         Print("DATASET INIT FAILED: lookback must be between 1 and 600 seconds");
         return INIT_PARAMETERS_INCORRECT;
      }

      string source_id=DatasetSourceId;
      if(source_id=="")
         source_id=StringFormat("mt5-%I64d-%I64u",(long)TimeLocal(),GetTickCount64());

      string filename=StringFormat("veltrix_%s.csv",_Symbol);
      if(!g_feature_pipeline.Init(_Symbol,source_id,filename,
                                  (ulong)FeatureLookbackSeconds*1000,
                                  MaxQuoteAgeMilliseconds,
                                  FeatureMinObservations,
                                  FeatureBufferCapacity,reason))
      {
         Print("DATASET INIT FAILED: ",reason);
         return INIT_FAILED;
      }
      PrintFormat("DATASET COLLECTION ENABLED | symbol=%s source=%s file=%s lookback=%d seconds min_observations=%d capacity=%d",
                  _Symbol,source_id,filename,(int)FeatureLookbackSeconds,
                  FeatureMinObservations,FeatureBufferCapacity);
   }

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

   if(EnableDatasetCollection && healthy && !g_dataset_fault_reported)
   {
      bool row_written=false;
      string pipeline_reason;
      if(!g_feature_pipeline.ProcessQuote(_Symbol,quote.tick,row_written,pipeline_reason))
      {
         Print("DATASET COLLECTION FAULTED | ",pipeline_reason);
         g_dataset_fault_reported=true;
      }
      else if(row_written && g_feature_pipeline.RowsWritten()%500==0)
      {
         PrintFormat("DATASET COLLECTION PROGRESS | symbol=%s rows=%I64d",
                     _Symbol,g_feature_pipeline.RowsWritten());
      }
   }

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
   if(EnableDatasetCollection)
      PrintFormat("DATASET COLLECTION STOPPED | rows=%I64d faulted=%s",
                  g_feature_pipeline.RowsWritten(),
                  (g_feature_pipeline.IsFaulted() ? "true" : "false"));
   Print("VELTRIX safe foundation stopped. No trading actions were available.");
}
