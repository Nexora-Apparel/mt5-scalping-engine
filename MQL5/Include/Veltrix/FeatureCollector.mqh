//+------------------------------------------------------------------+
//| FeatureCollector.mqh                                              |
//| Point-in-time quote features; research/data collection only.     |
//+------------------------------------------------------------------+
#ifndef VELTRIX_FEATURE_COLLECTOR_MQH
#define VELTRIX_FEATURE_COLLECTOR_MQH

struct VxQuoteObservation
{
   long time_msc;
   double bid;
   double ask;
};

struct VxFeatureCollectorConfig
{
   string symbol;
   ulong lookback_ms;
   ulong max_quote_age_ms;
   int min_observations;
   int capacity;
};

class CVxFeatureCollector
{
private:
   VxQuoteObservation m_quotes[];
   string m_symbol;
   ulong m_lookback_ms;
   ulong m_max_quote_age_ms;
   int m_min_observations;
   int m_capacity;
   long m_last_time_msc;
   bool m_initialized;

   bool ValidConfig(const VxFeatureCollectorConfig &config,string &reason) const
   {
      if(config.symbol!="XAUUSD" && config.symbol!="XAGUSD")
      {
         reason="Collector supports exact XAUUSD or XAGUSD symbol names only";
         return false;
      }
      if(config.lookback_ms==0 || config.max_quote_age_ms==0 ||
         config.min_observations<2 || config.capacity<config.min_observations ||
         config.capacity>100000)
      {
         reason="Feature collector configuration is invalid";
         return false;
      }
      reason="";
      return true;
   }

public:
   CVxFeatureCollector()
   {
      m_symbol="";
      m_lookback_ms=0;
      m_max_quote_age_ms=0;
      m_min_observations=0;
      m_capacity=0;
      m_last_time_msc=0;
      m_initialized=false;
   }

   bool Init(const VxFeatureCollectorConfig &config,string &reason)
   {
      m_initialized=false;
      if(!ValidConfig(config,reason))
         return false;
      ArrayResize(m_quotes,0);
      m_symbol=config.symbol;
      m_lookback_ms=config.lookback_ms;
      m_max_quote_age_ms=config.max_quote_age_ms;
      m_min_observations=config.min_observations;
      m_capacity=config.capacity;
      m_last_time_msc=0;
      m_initialized=true;
      reason="";
      return true;
   }

   // Call once per newly timestamped quote. Duplicate and out-of-order
   // timestamps are rejected rather than silently rewriting history.
   bool PushQuote(const string symbol,const double bid,const double ask,
                  const long time_msc,string &reason)
   {
      if(!m_initialized)
      {
         reason="Feature collector is not initialized";
         return false;
      }
      if(symbol!=m_symbol)
      {
         reason="Quote symbol does not match this collector";
         return false;
      }
      if(time_msc<=0 || time_msc<=m_last_time_msc)
      {
         reason="Quote timestamp is duplicate, invalid, or out of order";
         return false;
      }
      if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) ||
         bid<=0.0 || ask<=bid)
      {
         reason="Quote bid/ask is invalid or crossed";
         return false;
      }

      int count=ArraySize(m_quotes);
      if(count>=m_capacity)
      {
         for(int i=1;i<count;i++)
            m_quotes[i-1]=m_quotes[i];
         count--;
         ArrayResize(m_quotes,count);
      }
      if(ArrayResize(m_quotes,count+1)!=count+1)
      {
         reason="Unable to allocate quote observation";
         return false;
      }
      m_quotes[count].time_msc=time_msc;
      m_quotes[count].bid=bid;
      m_quotes[count].ask=ask;
      m_last_time_msc=time_msc;
      reason="";
      return true;
   }

   // Builds features using observations no later than evaluation_time_msc.
   // Returns false for insufficient or incomplete history; never fills gaps
   // with future observations or synthetic prices.
   bool BuildSnapshot(const long evaluation_time_msc,
                      VxStrategySnapshot &snapshot,string &reason) const
   {
      if(!m_initialized || evaluation_time_msc<=0)
      {
         reason="Collector or evaluation timestamp is invalid";
         return false;
      }
      int count=ArraySize(m_quotes);
      if(count<m_min_observations)
      {
         reason="Insufficient quote observations";
         return false;
      }

      int last=-1;
      for(int i=count-1;i>=0;i--)
      {
         if(m_quotes[i].time_msc<=evaluation_time_msc)
         {
            last=i;
            break;
         }
      }
      if(last<0)
      {
         reason="No quote exists at or before evaluation time";
         return false;
      }

      long latest_time=m_quotes[last].time_msc;
      if((ulong)(evaluation_time_msc-latest_time)>m_max_quote_age_ms)
      {
         reason="Latest quote is stale at evaluation time";
         return false;
      }
      long required_start=latest_time-(long)m_lookback_ms;
      int first=-1;
      for(int i=last;i>=0;i--)
      {
         if(m_quotes[i].time_msc<=required_start)
         {
            first=i;
            break;
         }
      }
      if(first<0 || last-first+1<m_min_observations)
      {
         reason="Stored observations do not cover the complete lookback";
         return false;
      }

      double first_mid=(m_quotes[first].bid+m_quotes[first].ask)/2.0;
      double last_mid=(m_quotes[last].bid+m_quotes[last].ask)/2.0;
      if(!MathIsValidNumber(first_mid) || !MathIsValidNumber(last_mid) ||
         first_mid<=0.0 || last_mid<=0.0)
      {
         reason="Mid-price is invalid or non-finite";
         return false;
      }

      double sum_squared_log_returns=0.0;
      double path_length=0.0;
      double previous_mid=first_mid;
      int observations=last-first+1;
      for(int i=first+1;i<=last;i++)
      {
         double mid=(m_quotes[i].bid+m_quotes[i].ask)/2.0;
         if(!MathIsValidNumber(mid) || mid<=0.0 ||
            !MathIsValidNumber(previous_mid) || previous_mid<=0.0)
         {
            reason="Invalid mid-price in feature window";
            return false;
         }
         double log_return=MathLog(mid/previous_mid);
         if(!MathIsValidNumber(log_return))
         {
            reason="Log return is invalid or non-finite";
            return false;
         }
         sum_squared_log_returns+=log_return*log_return;
         path_length+=MathAbs(mid-previous_mid);
         if(!MathIsValidNumber(sum_squared_log_returns) ||
            !MathIsValidNumber(path_length))
         {
            reason="Feature accumulation overflowed or became non-finite";
            return false;
         }
         previous_mid=mid;
      }

      double momentum_bps=MathLog(last_mid/first_mid)*10000.0;
      double realized_volatility_bps=MathSqrt(sum_squared_log_returns)*10000.0;
      double efficiency=(path_length>0.0 ?
                         MathAbs(last_mid-first_mid)/path_length : 0.0);
      if(!MathIsValidNumber(momentum_bps) ||
         !MathIsValidNumber(realized_volatility_bps) ||
         !MathIsValidNumber(efficiency) || efficiency<0.0 || efficiency>1.0)
      {
         reason="Calculated feature value is invalid";
         return false;
      }

      snapshot.symbol=m_symbol;
      snapshot.quote_time_msc=latest_time;
      snapshot.feature_window_start_msc=m_quotes[first].time_msc;
      snapshot.evaluation_time_msc=evaluation_time_msc;
      snapshot.bid=m_quotes[last].bid;
      snapshot.ask=m_quotes[last].ask;
      snapshot.momentum_bps=momentum_bps;
      snapshot.realized_volatility_bps=realized_volatility_bps;
      snapshot.efficiency_ratio=efficiency;
      snapshot.observations=observations;
      reason="";
      return true;
   }

   int Count() const
   {
      return ArraySize(m_quotes);
   }

   void Clear()
   {
      ArrayResize(m_quotes,0);
      m_last_time_msc=0;
   }
};

#endif
