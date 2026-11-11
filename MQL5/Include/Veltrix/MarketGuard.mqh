//+------------------------------------------------------------------+
//| MarketGuard.mqh                                                  |
//| Read-only symbol metadata and quote-health primitives.          |
//| No trading or order-submission functions are defined here.       |
//+------------------------------------------------------------------+
#ifndef VELTRIX_MARKET_GUARD_MQH
#define VELTRIX_MARKET_GUARD_MQH

struct VxSymbolSpec
{
   string symbol;
   double point;
   double tick_size;
   double tick_value_loss;
   double volume_min;
   double volume_max;
   double volume_step;
   long   stops_level_points;
   long   freeze_level_points;
   long   trade_mode;
   long   execution_mode;
   long   filling_mode;
};

struct VxQuoteSnapshot
{
   MqlTick tick;
   double  spread_points;
   long    broker_quote_age_ms;
   ulong   local_unchanged_age_ms;
};

class CVxMarketGuard
{
private:
   string m_symbol;
   ulong  m_max_quote_age_ms;
   double m_max_spread_points;
   long   m_last_tick_msc;
   ulong  m_last_tick_seen_ms;

public:
   CVxMarketGuard(void)
   {
      m_symbol="";
      m_max_quote_age_ms=0;
      m_max_spread_points=0.0;
      m_last_tick_msc=0;
      m_last_tick_seen_ms=0;
   }

   bool Init(const string symbol,
             const ulong max_quote_age_ms,
             const double max_spread_points)
   {
      if(symbol=="" || max_quote_age_ms==0 || max_spread_points<=0.0)
         return false;
      if(!SymbolSelect(symbol,true))
         return false;

      m_symbol=symbol;
      m_max_quote_age_ms=max_quote_age_ms;
      m_max_spread_points=max_spread_points;
      m_last_tick_msc=0;
      m_last_tick_seen_ms=0;
      return true;
   }

   bool ReadSymbolSpec(VxSymbolSpec &spec,string &reason)
   {
      reason="";
      if(m_symbol=="")
      {
         reason="Market guard is not initialized";
         return false;
      }

      spec.symbol=m_symbol;
      if(!SymbolInfoDouble(m_symbol,SYMBOL_POINT,spec.point) ||
         !SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE,spec.tick_size) ||
         !SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_VALUE_LOSS,spec.tick_value_loss) ||
         !SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MIN,spec.volume_min) ||
         !SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MAX,spec.volume_max) ||
         !SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_STEP,spec.volume_step) ||
         !SymbolInfoInteger(m_symbol,SYMBOL_TRADE_STOPS_LEVEL,spec.stops_level_points) ||
         !SymbolInfoInteger(m_symbol,SYMBOL_TRADE_FREEZE_LEVEL,spec.freeze_level_points) ||
         !SymbolInfoInteger(m_symbol,SYMBOL_TRADE_MODE,spec.trade_mode) ||
         !SymbolInfoInteger(m_symbol,SYMBOL_TRADE_EXEMODE,spec.execution_mode) ||
         !SymbolInfoInteger(m_symbol,SYMBOL_FILLING_MODE,spec.filling_mode))
      {
         reason="Broker symbol metadata could not be read completely";
         return false;
      }

      if(spec.point<=0.0 || spec.tick_size<=0.0 ||
         spec.tick_value_loss<=0.0 || spec.volume_min<=0.0 ||
         spec.volume_max<spec.volume_min || spec.volume_step<=0.0)
      {
         reason="Broker symbol metadata contains invalid or unsupported values";
         return false;
      }
      return true;
   }

   bool ReadQuote(VxQuoteSnapshot &snapshot,string &reason)
   {
      reason="";
      if(m_symbol=="")
      {
         reason="Market guard is not initialized";
         return false;
      }

      if(!SymbolInfoTick(m_symbol,snapshot.tick))
      {
         reason="No tick is available";
         return false;
      }
      if(snapshot.tick.bid<=0.0 || snapshot.tick.ask<=0.0 ||
         snapshot.tick.ask<snapshot.tick.bid || snapshot.tick.time_msc<=0)
      {
         reason="Tick has invalid bid, ask, or timestamp";
         return false;
      }

      double point=SymbolInfoDouble(m_symbol,SYMBOL_POINT);
      if(point<=0.0)
      {
         reason="Symbol point size is unavailable";
         return false;
      }

      snapshot.spread_points=(snapshot.tick.ask-snapshot.tick.bid)/point;
      if(snapshot.spread_points<=0.0 ||
         snapshot.spread_points>m_max_spread_points)
      {
         reason="Live bid/ask spread is outside the configured limit";
         return false;
      }

      datetime server_now=TimeTradeServer();
      if(server_now<=0)
      {
         reason="Broker server time is unavailable";
         return false;
      }
      long server_age=(long)server_now*1000-snapshot.tick.time_msc;
      snapshot.broker_quote_age_ms=server_age;
      if(server_age<0 || (ulong)server_age>m_max_quote_age_ms)
      {
         reason="Quote timestamp is stale or ahead of broker time";
         return false;
      }

      ulong local_now=GetTickCount64();
      if(snapshot.tick.time_msc!=m_last_tick_msc)
      {
         m_last_tick_msc=snapshot.tick.time_msc;
         m_last_tick_seen_ms=local_now;
      }
      if(m_last_tick_seen_ms==0)
      {
         reason="Local quote observation has not been initialized";
         return false;
      }

      snapshot.local_unchanged_age_ms=local_now-m_last_tick_seen_ms;
      if(snapshot.local_unchanged_age_ms>m_max_quote_age_ms)
      {
         reason="No newer broker tick has arrived within the freshness window";
         return false;
      }
      return true;
   }

   string Symbol(void) const
   {
      return m_symbol;
   }
};

#endif
