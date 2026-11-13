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
#include "..\\Include\\Veltrix\\RiskControls.mqh"
#include "..\\Include\\Veltrix\\PositionRegistry.mqh"
#include "..\\Include\\Veltrix\\ExecutionGuard.mqh"
#include "..\\Include\\Veltrix\\BrokerReconciler.mqh"
#include "..\\Include\\Veltrix\\ExecutionCoordinator.mqh"
#include "..\\Include\\Veltrix\\StrategyResearch.mqh"
#include "..\\Include\\Veltrix\\CandidateAnalysis.mqh"
#include "..\\Include\\Veltrix\\CandidateWindowBuilder.mqh"
#include "..\\Include\\Veltrix\\FeatureCollector.mqh"
#include "..\\Include\\Veltrix\\FeatureDatasetExporter.mqh"
#include "..\\Include\\Veltrix\\FeaturePipeline.mqh"

input ulong  MaxQuoteAgeMilliseconds = 2500;
input double MaxSpreadPoints        = 50.0;
input uint   HealthPollMilliseconds = 250;
input bool   EnableDatasetCollection = false;
input bool   EnableCandidateAnalysis = false;
input int    CandidateHistoryCapacity = 120;
input uint   FeatureLookbackSeconds = 60;
input int    FeatureMinObservations = 10;
input int    FeatureBufferCapacity = 10000;
input string DatasetSourceId = "";
input long   ExpectedDemoLogin = 0;
input string ExpectedDemoServer = "";

CVxMarketGuard g_market;
CVxCandidateAnalysis g_candidate_analysis;
CVxCandidateWindowBuilder g_candidate_window_builder;
bool g_candidate_faulted=false;
CVxFeaturePipeline g_feature_pipeline;
bool g_dataset_fault_reported=false;
bool g_last_health_state=false;
string g_last_health_reason="";

int OnInit()
{
   if(EnableDatasetCollection)
   {
      if(ExpectedDemoLogin<=0)
      {
         Print("DATASET DEMO ACCOUNT GUARD FAILED: expected demo login is missing or invalid");
         return INIT_FAILED;
      }
      if(ExpectedDemoServer=="")
      {
         Print("DATASET DEMO ACCOUNT GUARD FAILED: expected demo server is missing");
         return INIT_FAILED;
      }

      // MT5 may attach the EA before its asynchronous broker login completes.
      // Wait a bounded period; never treat disconnected/default account data as valid.
      bool terminal_connected=false;
      for(int attempt=0; attempt<90; attempt++)
      {
         terminal_connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
         if(terminal_connected)
            break;
         if(IsStopped())
         {
            Print("DATASET DEMO ACCOUNT GUARD FAILED: EA stopped while waiting for broker connection");
            return INIT_FAILED;
         }
         if(attempt==0 || (attempt+1)%15==0)
            PrintFormat("DATASET CONNECTION WAIT | attempt=%d/90 connected=false",attempt+1);
         Sleep(1000);
      }

      long actual_login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
      long actual_trade_mode=(long)AccountInfoInteger(ACCOUNT_TRADE_MODE);
      string actual_server=AccountInfoString(ACCOUNT_SERVER);
      bool login_match=(ExpectedDemoLogin>0 && actual_login==ExpectedDemoLogin);
      bool server_match=(ExpectedDemoServer==actual_server);
      bool demo_mode=(actual_trade_mode==ACCOUNT_TRADE_MODE_DEMO);
      terminal_connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
      PrintFormat("DATASET ACCOUNT DIAGNOSTIC | expected_login=%I64d actual_login=%I64d login_match=%s expected_server=%s actual_server=%s server_match=%s trade_mode=%I64d demo_mode=%s terminal_connected=%s symbol=%s",
                  ExpectedDemoLogin,actual_login,(login_match ? "true" : "false"),
                  ExpectedDemoServer,actual_server,(server_match ? "true" : "false"),
                  actual_trade_mode,(demo_mode ? "true" : "false"),
                  (terminal_connected ? "true" : "false"),_Symbol);
      if(!terminal_connected)
      {
         Print("DATASET DEMO ACCOUNT GUARD FAILED: broker connection did not complete within 90 seconds");
         return INIT_FAILED;
      }
      if(!login_match)
      {
         Print("DATASET DEMO ACCOUNT GUARD FAILED: connected account login does not match configured demo login");
         return INIT_FAILED;
      }
      if(!demo_mode)
      {
         Print("DATASET DEMO ACCOUNT GUARD FAILED: connected account trade mode is not DEMO");
         return INIT_FAILED;
      }
      if(!server_match)
      {
         Print("DATASET DEMO ACCOUNT GUARD FAILED: connected broker server does not exactly match configured server");
         return INIT_FAILED;
      }
      Print("DATASET DEMO ACCOUNT GUARD PASSED: exact configured DEMO account verified; data collection only; no order submission");
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

   if(EnableCandidateAnalysis)
   {
      if(CandidateHistoryCapacity<80 || CandidateHistoryCapacity>100000)
      {
         Print("CANDIDATE ANALYSIS INIT FAILED: history capacity must be between 80 and 100000");
         return INIT_PARAMETERS_INCORRECT;
      }
      if(!g_candidate_window_builder.Init(_Symbol,CandidateHistoryCapacity,reason))
      {
         Print("CANDIDATE ANALYSIS INIT FAILED: ",reason);
         return INIT_FAILED;
      }
      PrintFormat("CANDIDATE ANALYSIS ENABLED | symbol=XAUUSD broker_symbol=%s completed_window_seconds=5 history_capacity=%d orders=false",
                  _Symbol,CandidateHistoryCapacity);
   }

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

   Print("VELTRIX CANDIDATE RESEARCH MODULE: XAUUSD-only formulas loaded; completed-window adapter required; no order APIs are called.");
   Print("VELTRIX SAFE MODE: market health, read-only reconciliation, and state-only execution coordination. No order APIs are called.");
   return INIT_SUCCEEDED;
}

void EmitCandidateSignal(const VxCandidateResearchSignal &signal)
{
   string direction=(signal.direction==VX_SIGNAL_LONG ? "LONG" :
                     (signal.direction==VX_SIGNAL_SHORT ? "SHORT" : "NONE"));
   PrintFormat("VELTRIX RESEARCH CANDIDATE | candidate=%s direction=%s horizon=%d lookback=%d threshold=%.4f compression_pct=%.1f strength=%.6f signal_end_msc=%I64d execution_authorized=false",
               signal.candidate_id,direction,signal.horizon_seconds,
               signal.lookback_seconds,signal.parameter_threshold,
               signal.compression_percentile,signal.signal_strength,
               signal.signal_window_end_msc);
}

void EvaluateCompletedCandidateWindow(const long evaluation_time_msc)
{
   VxCompletedFeatureWindow windows[];
   if(!g_candidate_window_builder.CopyCompletedWindows(windows))
      return;
   int count=ArraySize(windows);
   if(count<2) return;
   int current=count-1;
   int horizons[4]={5,15,30,60};
   int momentum_lookbacks[3]={5,10,15};
   double momentum_thresholds[3]={0.5,1.0,1.5};
   int mean_lookbacks[3]={15,30,60};
   double mean_thresholds[3]={1.0,1.5,2.0};
   int breakout_lookbacks[2]={30,60};
   double breakout_fractions[3]={0.25,0.5,1.0};
   double compression_percentiles[2]={25.0,35.0};
   VxCandidateResearchSignal signal;
   string reason;

   for(int a=0;a<3;a++)
      for(int b=0;b<3;b++)
         for(int h=0;h<4;h++)
         {
            if(g_candidate_analysis.EvaluateMomentum("XAUUSD",windows,current,
               momentum_lookbacks[a],momentum_thresholds[b],horizons[h],
               evaluation_time_msc,signal,reason) && signal.emitted)
               EmitCandidateSignal(signal);
         }

   for(int a=0;a<3;a++)
      for(int b=0;b<3;b++)
         for(int h=0;h<4;h++)
         {
            if(g_candidate_analysis.EvaluateMeanReversion("XAUUSD",windows,current,
               mean_lookbacks[a],mean_thresholds[b],horizons[h],
               evaluation_time_msc,signal,reason) && signal.emitted)
               EmitCandidateSignal(signal);
         }

   for(int a=0;a<2;a++)
      for(int b=0;b<3;b++)
         for(int p=0;p<2;p++)
            for(int h=0;h<4;h++)
            {
               if(g_candidate_analysis.EvaluateVolatilityBreakout("XAUUSD",windows,current,
                  breakout_lookbacks[a],breakout_fractions[b],compression_percentiles[p],
                  horizons[h],evaluation_time_msc,signal,reason) && signal.emitted)
                  EmitCandidateSignal(signal);
            }
}

bool IsFreshCandidateTick(const MqlTick &tick,string &reason)
{
   if(tick.time_msc<=0 || tick.bid<=0.0 || tick.ask<=tick.bid ||
      !MathIsValidNumber(tick.bid) || !MathIsValidNumber(tick.ask))
   { reason="Candidate quote is invalid"; return false; }
   datetime server_now=TimeTradeServer();
   if(server_now<=0)
   { reason="Broker server time is unavailable"; return false; }
   long age=(long)server_now*1000-tick.time_msc+999;
   if(age<0 || (ulong)age>MaxQuoteAgeMilliseconds)
   { reason="Candidate quote is stale or ahead of broker time"; return false; }
   reason="";
   return true;
}

void OnTick()
{
   if(!EnableCandidateAnalysis || g_candidate_faulted)
      return;
   MqlTick tick;
   string reason;
   if(!SymbolInfoTick(_Symbol,tick) || !IsFreshCandidateTick(tick,reason))
      return;
   bool window_completed=false;
   if(!g_candidate_window_builder.PushQuote(_Symbol,tick,window_completed,reason))
   {
      g_candidate_faulted=true;
      Print("CANDIDATE ANALYSIS FAULTED | ",reason);
      return;
   }
   if(window_completed)
      EvaluateCompletedCandidateWindow(tick.time_msc);
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
   if(EnableCandidateAnalysis)
      PrintFormat("CANDIDATE ANALYSIS STOPPED | completed_windows=%d faulted=%s",
                  g_candidate_window_builder.Count(),
                  (g_candidate_faulted ? "true" : "false"));
   if(EnableDatasetCollection)
      PrintFormat("DATASET COLLECTION STOPPED | rows=%I64d faulted=%s",
                  g_feature_pipeline.RowsWritten(),
                  (g_feature_pipeline.IsFaulted() ? "true" : "false"));
   Print("VELTRIX safe foundation stopped. No trading actions were available.");
}
