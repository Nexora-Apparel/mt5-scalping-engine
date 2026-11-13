//+------------------------------------------------------------------+
//| CandidateAnalysis.mqh                                            |
//| Frozen XAUUSD candidate formulas; completed windows only.       |
//| Research-only: no order or execution APIs.                       |
//+------------------------------------------------------------------+
#ifndef VELTRIX_CANDIDATE_ANALYSIS_MQH
#define VELTRIX_CANDIDATE_ANALYSIS_MQH

#include "StrategyResearch.mqh"

struct VxCompletedFeatureWindow
{
   long window_start_msc;
   double mid_high;
   double mid_low;
   double mid_close;
   double realized_volatility_bps;
   bool valid;
};

struct VxCandidateResearchSignal
{
   bool emitted;
   ENUM_VX_SIGNAL_DIRECTION direction;
   string candidate_id;
   string symbol;
   long signal_window_start_msc;
   long signal_window_end_msc;
   long evaluated_at_msc;
   int horizon_seconds;
   double signal_strength;
   string reason;
};

class CVxCandidateAnalysis
{
private:
   bool AllowedHorizon(const int horizon_seconds) const
   {
      return (horizon_seconds==5 || horizon_seconds==15 ||
              horizon_seconds==30 || horizon_seconds==60);
   }

   void ResetSignal(VxCandidateResearchSignal &signal,
                    const string candidate_id,
                    const string symbol,
                    const int horizon_seconds) const
   {
      signal.emitted=false;
      signal.direction=VX_SIGNAL_NONE;
      signal.candidate_id=candidate_id;
      signal.symbol=symbol;
      signal.signal_window_start_msc=0;
      signal.signal_window_end_msc=0;
      signal.evaluated_at_msc=0;
      signal.horizon_seconds=horizon_seconds;
      signal.signal_strength=0.0;
      signal.reason="";
   }

   bool ValidWindow(const VxCompletedFeatureWindow &window) const
   {
      if(!window.valid || window.window_start_msc<=0)
         return false;
      if(!MathIsValidNumber(window.mid_high) ||
         !MathIsValidNumber(window.mid_low) ||
         !MathIsValidNumber(window.mid_close) ||
         !MathIsValidNumber(window.realized_volatility_bps))
         return false;
      if(window.mid_low<=0.0 || window.mid_high<window.mid_low ||
         window.mid_close<window.mid_low || window.mid_close>window.mid_high ||
         window.realized_volatility_bps<0.0)
         return false;
      return true;
   }

   bool Contiguous(const VxCompletedFeatureWindow &windows[],
                   const int first_index,const int last_index) const
   {
      int count=ArraySize(windows);
      if(first_index<0 || last_index<first_index || last_index>=count)
         return false;
      for(int i=first_index;i<=last_index;i++)
      {
         if(!ValidWindow(windows[i]))
            return false;
         if(i>first_index &&
            windows[i].window_start_msc-windows[i-1].window_start_msc!=5000)
            return false;
      }
      return true;
   }

   bool VolatilityScale(const VxCompletedFeatureWindow &windows[],
                        const int start_index,const int end_exclusive,
                        double &scale) const
   {
      scale=0.0;
      if(start_index<0 || end_exclusive<=start_index ||
         end_exclusive>ArraySize(windows))
         return false;
      double sum=0.0;
      for(int i=start_index;i<end_exclusive;i++)
      {
         double value=windows[i].realized_volatility_bps;
         if(!MathIsValidNumber(value) || value<0.0)
            return false;
         sum+=value*value;
         if(!MathIsValidNumber(sum))
            return false;
      }
      scale=MathSqrt(sum);
      return (MathIsValidNumber(scale) && scale>0.0);
   }

   bool PriorRangeWidth(const VxCompletedFeatureWindow &windows[],
                        const int end_exclusive,const int lookback_windows,
                        double &width_bps) const
   {
      width_bps=0.0;
      int start=end_exclusive-lookback_windows;
      if(start<0 || end_exclusive>ArraySize(windows) ||
         !Contiguous(windows,start,end_exclusive-1))
         return false;
      double high=windows[start].mid_high;
      double low=windows[start].mid_low;
      double reference=windows[start].mid_close;
      if(reference<=0.0)
         return false;
      for(int i=start+1;i<end_exclusive;i++)
      {
         high=MathMax(high,windows[i].mid_high);
         low=MathMin(low,windows[i].mid_low);
      }
      width_bps=(high-low)/reference*10000.0;
      return (MathIsValidNumber(width_bps) && width_bps>=0.0);
   }

   bool Percentile(const double &values[],const double percentile,
                   double &result) const
   {
      int count=ArraySize(values);
      if(count<1 || percentile<0.0 || percentile>100.0)
         return false;
      double sorted[];
      if(ArrayResize(sorted,count)!=count)
         return false;
      for(int i=0;i<count;i++)
      {
         if(!MathIsValidNumber(values[i]))
            return false;
         sorted[i]=values[i];
      }
      ArraySort(sorted);
      double position=(count-1)*percentile/100.0;
      int low=(int)MathFloor(position);
      int high=(int)MathCeil(position);
      if(low==high)
         result=sorted[low];
      else
         result=sorted[low]+(sorted[high]-sorted[low])*(position-low);
      return MathIsValidNumber(result);
   }

   bool ValidCommon(const string canonical_symbol,
                    const int horizon_seconds,
                    const long evaluation_time_msc,
                    const VxCompletedFeatureWindow &windows[],
                    const int current_index,
                    VxCandidateResearchSignal &signal,
                    const string candidate_id,
                    string &reason) const
   {
      ResetSignal(signal,candidate_id,canonical_symbol,horizon_seconds);
      if(canonical_symbol!="XAUUSD")
         reason="Only canonical XAUUSD candidate analysis is permitted";
      else if(!AllowedHorizon(horizon_seconds))
         reason="Holding horizon is not preregistered";
      else if(evaluation_time_msc<=0)
         reason="Evaluation timestamp is invalid";
      else if(current_index<0 || current_index>=ArraySize(windows))
         reason="Current completed-window index is invalid";
      else if(!Contiguous(windows,current_index,current_index))
         reason="Current feature window is invalid";
      else if(evaluation_time_msc<windows[current_index].window_start_msc+5000)
         reason="Current five-second feature window is not complete";
      else
      {
         reason="";
         return true;
      }
      signal.reason=reason;
      return false;
   }

   void SetSignal(VxCandidateResearchSignal &signal,
                  const VxCompletedFeatureWindow &window,
                  const long evaluation_time_msc,
                  const ENUM_VX_SIGNAL_DIRECTION direction,
                  const double strength,
                  const string reason) const
   {
      signal.emitted=true;
      signal.direction=direction;
      signal.signal_window_start_msc=window.window_start_msc;
      signal.signal_window_end_msc=window.window_start_msc+5000;
      signal.evaluated_at_msc=evaluation_time_msc;
      signal.signal_strength=strength;
      signal.reason=reason;
   }

public:
   bool EvaluateMomentum(const string canonical_symbol,
                        const VxCompletedFeatureWindow &windows[],
                        const int current_index,
                        const int lookback_seconds,
                        const double standardized_threshold,
                        const int horizon_seconds,
                        const long evaluation_time_msc,
                        VxCandidateResearchSignal &signal,
                        string &reason) const
   {
      if(!ValidCommon(canonical_symbol,horizon_seconds,evaluation_time_msc,
                      windows,current_index,signal,
                      "XAU_MOMENTUM_CONTINUATION_V1",reason))
         return false;
      if((lookback_seconds!=5 && lookback_seconds!=10 && lookback_seconds!=15) ||
         !MathIsValidNumber(standardized_threshold) || standardized_threshold<=0.0)
      { reason="Momentum lookback or threshold is invalid"; signal.reason=reason; return false; }
      int n=lookback_seconds/5;
      if(current_index<n ||
         !Contiguous(windows,current_index-n,current_index))
      { reason="Momentum lookback history is incomplete or discontinuous"; signal.reason=reason; return false; }
      double scale=0.0;
      if(!VolatilityScale(windows,current_index-n,current_index,scale))
      { reason="Momentum trailing volatility scale is unavailable"; signal.reason=reason; return false; }
      double previous=windows[current_index-n].mid_close;
      double current=windows[current_index].mid_close;
      double z=MathLog(current/previous)*10000.0/scale;
      if(!MathIsValidNumber(z))
      { reason="Momentum standardized return is invalid"; signal.reason=reason; return false; }
      if(MathAbs(z)<standardized_threshold)
      { reason="Momentum threshold not met"; signal.reason=reason; return true; }
      SetSignal(signal,windows[current_index],evaluation_time_msc,
                (z>0.0 ? VX_SIGNAL_LONG : VX_SIGNAL_SHORT),z,
                "Research candidate only; not an execution instruction");
      reason="";
      return true;
   }

   bool EvaluateMeanReversion(const string canonical_symbol,
                              const VxCompletedFeatureWindow &windows[],
                              const int current_index,
                              const int lookback_seconds,
                              const double standardized_threshold,
                              const int horizon_seconds,
                              const long evaluation_time_msc,
                              VxCandidateResearchSignal &signal,
                              string &reason) const
   {
      if(!ValidCommon(canonical_symbol,horizon_seconds,evaluation_time_msc,
                      windows,current_index,signal,
                      "XAU_MEAN_REVERSION_V1",reason))
         return false;
      if((lookback_seconds!=15 && lookback_seconds!=30 && lookback_seconds!=60) ||
         !MathIsValidNumber(standardized_threshold) || standardized_threshold<=0.0)
      { reason="Mean-reversion lookback or threshold is invalid"; signal.reason=reason; return false; }
      int n=lookback_seconds/5;
      if(current_index<n ||
         !Contiguous(windows,current_index-n,current_index))
      { reason="Mean-reversion history is incomplete or discontinuous"; signal.reason=reason; return false; }
      double scale=0.0;
      if(!VolatilityScale(windows,current_index-n,current_index,scale))
      { reason="Mean-reversion trailing volatility scale is unavailable"; signal.reason=reason; return false; }
      double reference=0.0;
      for(int i=current_index-n;i<current_index;i++)
         reference+=windows[i].mid_close;
      reference/=n;
      double z=MathLog(windows[current_index].mid_close/reference)*10000.0/scale;
      if(!MathIsValidNumber(z))
      { reason="Mean-reversion standardized displacement is invalid"; signal.reason=reason; return false; }
      if(MathAbs(z)<standardized_threshold)
      { reason="Mean-reversion threshold not met"; signal.reason=reason; return true; }
      SetSignal(signal,windows[current_index],evaluation_time_msc,
                (z>0.0 ? VX_SIGNAL_SHORT : VX_SIGNAL_LONG),MathAbs(z),
                "Research candidate only; not an execution instruction");
      reason="";
      return true;
   }

   bool EvaluateVolatilityBreakout(const string canonical_symbol,
                                   const VxCompletedFeatureWindow &windows[],
                                   const int current_index,
                                   const int lookback_seconds,
                                   const double distance_fraction,
                                   const double compression_percentile,
                                   const int horizon_seconds,
                                   const long evaluation_time_msc,
                                   VxCandidateResearchSignal &signal,
                                   string &reason) const
   {
      if(!ValidCommon(canonical_symbol,horizon_seconds,evaluation_time_msc,
                      windows,current_index,signal,
                      "XAU_VOLATILITY_BREAKOUT_V1",reason))
         return false;
      if((lookback_seconds!=30 && lookback_seconds!=60) ||
         !MathIsValidNumber(distance_fraction) || distance_fraction<=0.0 ||
         !MathIsValidNumber(compression_percentile) ||
         (compression_percentile!=25.0 && compression_percentile!=35.0))
      { reason="Breakout lookback or registered thresholds are invalid"; signal.reason=reason; return false; }
      int n=lookback_seconds/5;
      if(current_index<60+n ||
         !Contiguous(windows,current_index-60-n,current_index))
      { reason="Breakout or 60-window compression history is incomplete or discontinuous"; signal.reason=reason; return false; }
      double scale=0.0;
      if(!VolatilityScale(windows,current_index-n,current_index,scale))
      { reason="Breakout trailing volatility scale is unavailable"; signal.reason=reason; return false; }
      double current_range=0.0;
      if(!PriorRangeWidth(windows,current_index,n,current_range))
      { reason="Breakout prior range is invalid"; signal.reason=reason; return false; }
      double history[60];
      for(int k=0;k<60;k++)
      {
         if(!PriorRangeWidth(windows,current_index-60+k,n,history[k]))
         { reason="Breakout compression reference contains an invalid range"; signal.reason=reason; return false; }
      }
      double cutoff=0.0;
      if(!Percentile(history,compression_percentile,cutoff))
      { reason="Breakout compression percentile could not be calculated"; signal.reason=reason; return false; }
      if(current_range>cutoff)
      { reason="Prior range is not compressed"; signal.reason=reason; return true; }
      double prior_high=windows[current_index-n].mid_high;
      double prior_low=windows[current_index-n].mid_low;
      for(int i=current_index-n+1;i<current_index;i++)
      {
         prior_high=MathMax(prior_high,windows[i].mid_high);
         prior_low=MathMin(prior_low,windows[i].mid_low);
      }
      double current=windows[current_index].mid_close;
      double long_distance=(current>prior_high ? MathLog(current/prior_high)*10000.0 : 0.0);
      double short_distance=(current<prior_low ? MathLog(prior_low/current)*10000.0 : 0.0);
      double required=distance_fraction*scale;
      if(long_distance>=required)
         SetSignal(signal,windows[current_index],evaluation_time_msc,VX_SIGNAL_LONG,
                   long_distance/scale,"Research candidate only; not an execution instruction");
      else if(short_distance>=required)
         SetSignal(signal,windows[current_index],evaluation_time_msc,VX_SIGNAL_SHORT,
                   short_distance/scale,"Research candidate only; not an execution instruction");
      else
      { reason="Breakout distance threshold not met"; signal.reason=reason; return true; }
      reason="";
      return true;
   }
};

#endif
