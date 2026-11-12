//+------------------------------------------------------------------+
//| StrategyResearch.mqh                                             |
//| XAUUSD-only deterministic candidate evaluator; no trade APIs.   |
//+------------------------------------------------------------------+
#ifndef VELTRIX_STRATEGY_RESEARCH_MQH
#define VELTRIX_STRATEGY_RESEARCH_MQH

enum ENUM_VX_SIGNAL_DIRECTION { VX_SIGNAL_NONE=0, VX_SIGNAL_LONG=1, VX_SIGNAL_SHORT=-1 };

struct VxStrategyConfig
{
   string symbol;
   ulong lookback_ms;
   ulong max_quote_age_ms;
   double max_spread_bps;
   double min_realized_volatility_bps;
   double max_realized_volatility_bps;
   double min_abs_momentum_bps;
   double min_efficiency_ratio;
   int min_observations;
};
struct VxStrategySnapshot
{
   string symbol;
   long quote_time_msc;
   long feature_window_start_msc;
   long evaluation_time_msc;
   double bid;
   double ask;
   double momentum_bps;
   double realized_volatility_bps;
   double efficiency_ratio;
   int observations;
};
struct VxSignalCandidate
{
   bool eligible;
   ENUM_VX_SIGNAL_DIRECTION direction;
   string symbol;
   long evaluated_at_msc;
   double spread_bps;
   double momentum_bps;
   double realized_volatility_bps;
   double efficiency_ratio;
   string reason;
};

class CVxStrategyResearch
{
private:
   bool ValidConfig(const VxStrategyConfig &config,string &reason) const
   {
      if(config.symbol!="XAUUSD")
      {
         reason="XAGUSD and all other instruments are disabled; XAUUSD only";
         return false;
      }
      if(config.lookback_ms==0 || config.max_quote_age_ms==0 ||
         !MathIsValidNumber(config.max_spread_bps) ||
         !MathIsValidNumber(config.min_realized_volatility_bps) ||
         !MathIsValidNumber(config.max_realized_volatility_bps) ||
         !MathIsValidNumber(config.min_abs_momentum_bps) ||
         !MathIsValidNumber(config.min_efficiency_ratio) ||
         config.max_spread_bps<=0.0 || config.min_realized_volatility_bps<0.0 ||
         config.max_realized_volatility_bps<=config.min_realized_volatility_bps ||
         config.min_abs_momentum_bps<=0.0 || config.min_efficiency_ratio<0.0 ||
         config.min_efficiency_ratio>1.0 || config.min_observations<2)
      { reason="Strategy configuration is invalid or incomplete"; return false; }
      reason="";
      return true;
   }
public:
   bool Evaluate(const VxStrategyConfig &config,const VxStrategySnapshot &snapshot,
                 VxSignalCandidate &candidate,string &reason) const
   {
      candidate.eligible=false;
      candidate.direction=VX_SIGNAL_NONE;
      candidate.symbol=snapshot.symbol;
      candidate.evaluated_at_msc=snapshot.evaluation_time_msc;
      candidate.spread_bps=0.0;
      candidate.momentum_bps=snapshot.momentum_bps;
      candidate.realized_volatility_bps=snapshot.realized_volatility_bps;
      candidate.efficiency_ratio=snapshot.efficiency_ratio;
      candidate.reason="";
      if(!ValidConfig(config,reason)) { candidate.reason=reason; return false; }
      if(snapshot.symbol!="XAUUSD")
         reason="Snapshot contains a non-XAUUSD instrument";
      else if(snapshot.symbol!=config.symbol)
         reason="Snapshot symbol does not match its independent configuration";
      else if(snapshot.evaluation_time_msc<=0 || snapshot.quote_time_msc<=0 ||
              snapshot.quote_time_msc>snapshot.evaluation_time_msc)
         reason="Quote timestamp is missing or lies after evaluation time";
      else if((ulong)(snapshot.evaluation_time_msc-snapshot.quote_time_msc)>config.max_quote_age_ms)
         reason="Quote is stale";
      else if(snapshot.bid<=0.0 || snapshot.ask<=snapshot.bid ||
              !MathIsValidNumber(snapshot.bid) || !MathIsValidNumber(snapshot.ask))
         reason="Bid/ask snapshot is invalid or crossed";
      else if(snapshot.feature_window_start_msc<=0 ||
              snapshot.feature_window_start_msc>snapshot.quote_time_msc ||
              (ulong)(snapshot.quote_time_msc-snapshot.feature_window_start_msc)<config.lookback_ms)
         reason="Feature window does not end after its quote or cover the configured lookback";
      else if(snapshot.observations<config.min_observations)
         reason="Insufficient observations for the configured lookback";
      else if(!MathIsValidNumber(snapshot.momentum_bps) ||
              !MathIsValidNumber(snapshot.realized_volatility_bps) ||
              !MathIsValidNumber(snapshot.efficiency_ratio) ||
              snapshot.realized_volatility_bps<0.0 ||
              snapshot.efficiency_ratio<0.0 || snapshot.efficiency_ratio>1.0)
         reason="Feature snapshot contains invalid values";
      else
      {
         double midpoint=(snapshot.bid+snapshot.ask)/2.0;
         if(!MathIsValidNumber(midpoint) || midpoint<=0.0)
            reason="Bid/ask midpoint is invalid or non-finite";
         else
         {
            candidate.spread_bps=((snapshot.ask-snapshot.bid)/midpoint)*10000.0;
            if(!MathIsValidNumber(candidate.spread_bps)) reason="Calculated spread is invalid or non-finite";
            else if(candidate.spread_bps>config.max_spread_bps) reason="Spread exceeds the research configuration limit";
            else if(snapshot.realized_volatility_bps<config.min_realized_volatility_bps ||
                    snapshot.realized_volatility_bps>config.max_realized_volatility_bps)
               reason="Realized volatility is outside the configured research band";
            else if(snapshot.efficiency_ratio<config.min_efficiency_ratio)
               reason="Directional efficiency is below the configured threshold";
            else if(MathAbs(snapshot.momentum_bps)<config.min_abs_momentum_bps)
               reason="Absolute momentum is below the configured threshold";
            else
            {
               candidate.direction=(snapshot.momentum_bps>0.0 ? VX_SIGNAL_LONG : VX_SIGNAL_SHORT);
               candidate.eligible=true;
               candidate.reason="XAUUSD research candidate passed configured feature gates; not an execution instruction";
               reason="";
               return true;
            }
         }
      }
      candidate.reason=reason;
      candidate.direction=VX_SIGNAL_NONE;
      candidate.eligible=false;
      return true;
   }
};
#endif
