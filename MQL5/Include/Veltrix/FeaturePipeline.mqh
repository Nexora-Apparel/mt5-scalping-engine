//+------------------------------------------------------------------+
//| FeaturePipeline.mqh                                              |
//| Optional XAUUSD-only live-quote research collection.             |
//+------------------------------------------------------------------+
#ifndef VELTRIX_FEATURE_PIPELINE_MQH
#define VELTRIX_FEATURE_PIPELINE_MQH
#include "FeatureCollector.mqh"
#include "FeatureDatasetExporter.mqh"
class CVxFeaturePipeline
{
private:
   CVxFeatureCollector m_collector;
   CVxFeatureDatasetExporter m_exporter;
   string m_symbol,m_source_id,m_filename;
   long m_last_quote_msc,m_last_export_msc,m_rows_written;
   bool m_initialized,m_faulted;
   string m_fault_reason;
   bool ValidSourceId(const string value) const
   {
      int n=StringLen(value);if(n<1||n>96)return false;
      for(int i=0;i<n;i++){ushort ch=StringGetCharacter(value,i);
       bool ok=((ch>='A'&&ch<='Z')||(ch>='a'&&ch<='z')||(ch>='0'&&ch<='9')||ch=='_'||ch=='-');
       if(!ok)return false;}return true;
   }
   bool ValidFileName(const string value) const
   {
      int n=StringLen(value);if(n<5||StringSubstr(value,n-4,4)!=".csv")return false;
      for(int i=0;i<n-4;i++){ushort ch=StringGetCharacter(value,i);
       bool ok=((ch>='A'&&ch<='Z')||(ch>='a'&&ch<='z')||(ch>='0'&&ch<='9')||ch=='_'||ch=='-');
       if(!ok)return false;}return true;
   }
public:
   CVxFeaturePipeline()
   {m_symbol="";m_source_id="";m_filename="";m_last_quote_msc=0;m_last_export_msc=0;
    m_rows_written=0;m_initialized=false;m_faulted=false;m_fault_reason="";}
   bool Init(const string symbol,const string source_id,const string filename,const ulong lookback_ms,
             const ulong max_quote_age_ms,const int min_observations,const int capacity,string &reason)
   {
      m_initialized=false;m_faulted=false;m_fault_reason="";m_last_quote_msc=0;m_last_export_msc=0;m_rows_written=0;
      if(symbol!="XAUUSD"||!ValidSourceId(source_id)||!ValidFileName(filename)||
         lookback_ms<1000||lookback_ms>600000||max_quote_age_ms==0||
         min_observations<2||capacity<min_observations||capacity>100000)
      {reason="Feature pipeline accepts XAUUSD only; configuration is invalid or instrument is unsupported";return false;}
      VxFeatureCollectorConfig config;
      config.symbol=symbol;config.lookback_ms=lookback_ms;config.max_quote_age_ms=max_quote_age_ms;
      config.min_observations=min_observations;config.capacity=capacity;
      if(!m_collector.Init(config,reason))return false;
      m_symbol=symbol;m_source_id=source_id;m_filename=filename;m_initialized=true;reason="";return true;
   }
   bool ProcessQuote(const string symbol,const MqlTick &tick,bool &row_written,string &reason)
   {
      row_written=false;reason="";
      if(!m_initialized){reason="Feature pipeline is not initialized";return false;}
      if(m_faulted){reason=m_fault_reason;return false;}
      if(symbol!="XAUUSD"||symbol!=m_symbol)
      {reason="Only the active XAUUSD pipeline accepts quotes";m_faulted=true;m_fault_reason=reason;return false;}
      if(tick.time_msc<=0){reason="Quote timestamp is invalid";m_faulted=true;m_fault_reason=reason;return false;}
      if(tick.time_msc<=m_last_quote_msc){reason="Duplicate or out-of-order quote ignored";return true;}
      if(!m_collector.PushQuote(symbol,tick.bid,tick.ask,tick.time_msc,reason))
      {m_faulted=true;m_fault_reason=reason;return false;}
      m_last_quote_msc=tick.time_msc;
      VxStrategySnapshot snapshot;
      if(!m_collector.BuildSnapshot(tick.time_msc,snapshot,reason))
      {
         if(reason=="Insufficient quote observations"||reason=="Stored observations do not cover the complete lookback")
         {reason="Collecting warm-up history";return true;}
         m_faulted=true;m_fault_reason=reason;return false;
      }
      if(snapshot.evaluation_time_msc<=m_last_export_msc){reason="Duplicate evaluation snapshot skipped";return true;}
      if(snapshot.quote_time_msc!=tick.time_msc||snapshot.evaluation_time_msc!=tick.time_msc)
      {reason="Snapshot timestamps do not match the source quote";m_faulted=true;m_fault_reason=reason;return false;}
      if(!m_exporter.AppendSnapshot(m_filename,m_source_id,snapshot,reason))
      {m_faulted=true;m_fault_reason=reason;return false;}
      m_last_export_msc=snapshot.evaluation_time_msc;m_rows_written++;row_written=true;reason="";return true;
   }
   long RowsWritten() const{return m_rows_written;}
   bool IsFaulted() const{return m_faulted;}
   string FaultReason() const{return m_fault_reason;}
   string SourceId() const{return m_source_id;}
   string FileName() const{return m_filename;}
};
#endif
