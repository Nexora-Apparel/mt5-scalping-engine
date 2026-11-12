//+------------------------------------------------------------------+
//| FeatureDatasetExporter.mqh                                       |
//| XAUUSD-only versioned CSV export for chronological research.    |
//+------------------------------------------------------------------+
#ifndef VELTRIX_FEATURE_DATASET_EXPORTER_MQH
#define VELTRIX_FEATURE_DATASET_EXPORTER_MQH
#include "StrategyResearch.mqh"
#define VX_FEATURE_DATASET_SCHEMA_VERSION "1"
#define VX_FEATURE_CALCULATION_VERSION "1.0.0"
class CVxFeatureDatasetExporter
{
private:
   bool SafeFileName(const string filename) const
   {
      int length=StringLen(filename);
      if(length<5||StringSubstr(filename,length-4,4)!=".csv")return false;
      for(int i=0;i<length-4;i++){ushort ch=StringGetCharacter(filename,i);
       bool allowed=((ch>='A'&&ch<='Z')||(ch>='a'&&ch<='z')||(ch>='0'&&ch<='9')||ch=='_'||ch=='-');
       if(!allowed)return false;}return true;
   }
   bool ValidateExistingHeader(const int handle) const
   {
      string expected[13]={"schema_version","feature_version","source_id","symbol","quote_time_msc",
       "window_start_msc","evaluation_time_msc","bid","ask","momentum_bps","realized_volatility_bps",
       "efficiency_ratio","observations"};
      if(!FileSeek(handle,0,SEEK_SET))return false;
      for(int i=0;i<ArraySize(expected);i++){if(FileIsEnding(handle)||FileReadString(handle)!=expected[i])return false;}
      return true;
   }
public:
   bool AppendSnapshot(const string filename,const string source_id,const VxStrategySnapshot &snapshot,string &reason) const
   {
      if(!SafeFileName(filename)){reason="Dataset filename must be a safe CSV basename";return false;}
      if(StringLen(source_id)<1||StringLen(source_id)>96||StringFind(source_id,",")>=0||
         StringFind(source_id,"\n")>=0||StringFind(source_id,"\r")>=0)
      {reason="Source identifier is missing or contains invalid delimiters";return false;}
      if(snapshot.symbol!="XAUUSD"||snapshot.quote_time_msc<=0||snapshot.feature_window_start_msc<=0||
         snapshot.evaluation_time_msc<snapshot.quote_time_msc||snapshot.feature_window_start_msc>snapshot.quote_time_msc||
         !MathIsValidNumber(snapshot.bid)||!MathIsValidNumber(snapshot.ask)||!MathIsValidNumber(snapshot.momentum_bps)||
         !MathIsValidNumber(snapshot.realized_volatility_bps)||!MathIsValidNumber(snapshot.efficiency_ratio)||
         snapshot.bid<=0.0||snapshot.ask<=snapshot.bid||snapshot.realized_volatility_bps<0.0||
         snapshot.efficiency_ratio<0.0||snapshot.efficiency_ratio>1.0||snapshot.observations<2)
      {reason="Snapshot failed XAUUSD-only dataset validation; XAGUSD is not accepted";return false;}
      int handle=FileOpen(filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
      if(handle==INVALID_HANDLE){reason="Unable to open dataset CSV in the terminal Files sandbox";return false;}
      bool ok=true;
      if(FileSize(handle)==0)
      {
         uint h=FileWrite(handle,"schema_version","feature_version","source_id","symbol","quote_time_msc",
          "window_start_msc","evaluation_time_msc","bid","ask","momentum_bps","realized_volatility_bps",
          "efficiency_ratio","observations");if(h==0)ok=false;
      }
      else if(!ValidateExistingHeader(handle)){FileClose(handle);reason="Existing CSV header does not match expected schema";return false;}
      if(ok&&!FileSeek(handle,0,SEEK_END))ok=false;
      if(ok)
      {
         uint written=FileWrite(handle,VX_FEATURE_DATASET_SCHEMA_VERSION,VX_FEATURE_CALCULATION_VERSION,
          source_id,snapshot.symbol,snapshot.quote_time_msc,snapshot.feature_window_start_msc,
          snapshot.evaluation_time_msc,DoubleToString(snapshot.bid,10),DoubleToString(snapshot.ask,10),
          DoubleToString(snapshot.momentum_bps,10),DoubleToString(snapshot.realized_volatility_bps,10),
          DoubleToString(snapshot.efficiency_ratio,10),snapshot.observations);if(written==0)ok=false;
      }
      FileFlush(handle);FileClose(handle);
      if(!ok){reason="CSV write or seek failed; inspect the terminal file and disk state";return false;}
      reason="";return true;
   }
};
#endif
