//+------------------------------------------------------------------+
//| CandidateSignalResearch.mqh                                      |
//| Frozen XAUUSD candidate formulas; analysis only, no trade APIs.  |
//+------------------------------------------------------------------+
#ifndef VELTRIX_CANDIDATE_SIGNAL_RESEARCH_MQH
#define VELTRIX_CANDIDATE_SIGNAL_RESEARCH_MQH

#define VX_CANDIDATE_WINDOW_MS 5000
#define VX_CANDIDATE_HISTORY 60

struct VxCompletedFeatureWindow
{
   string symbol;
   long start_msc;
   int window_seconds;
   bool completed;
   double mid_close;
   double mid_high;
   double mid_low;
   double realized_volatility_bps;
};

struct VxResearchSignal
{
   string candidate_id;
   int direction; // +1 long, -1 short; never an order instruction.
   long signal_window_end_msc;
   int horizon_seconds;
   int lookback_seconds;
   double threshold;
   double compression_percentile;
   double standardized_score;
   bool research_only;
};

class CVxCandidateSignalResearch
{
private:
   bool ValidWindow(const VxCompletedFeatureWindow &w) const
   {
      return w.symbol=="XAUUSD" && w.window_seconds==5 && w.completed &&
             w.start_msc>0 && MathIsValidNumber(w.mid_close) &&
             MathIsValidNumber(w.mid_high) && MathIsValidNumber(w.mid_low) &&
             MathIsValidNumber(w.realized_volatility_bps) &&
             w.mid_close>0.0 && w.mid_low>0.0 && w.mid_high>=w.mid_low &&
             w.mid_close>=w.mid_low && w.mid_close<=w.mid_high &&
             w.realized_volatility_bps>=0.0;
   }

   bool Consecutive(const VxCompletedFeatureWindow &w[],const int first,const int last) const
   {
      if(first<0 || last>=ArraySize(w) || first>=last) return false;
      for(int i=first+1;i<=last;i++)
         if(w[i].start_msc-w[i-1].start_msc!=VX_CANDIDATE_WINDOW_MS)
            return false;
      return true;
   }

   double Scale(const VxCompletedFeatureWindow &w[],const int first,const int last) const
   {
      if(first<0 || last>=ArraySize(w) || first>last) return 0.0;
      double sum=0.0;
      for(int i=first;i<=last;i++)
      {
         double v=w[i].realized_volatility_bps;
         if(!MathIsValidNumber(v) || v<0.0) return 0.0;
         sum+=v*v;
      }
      if(!MathIsValidNumber(sum) || sum<=0.0) return 0.0;
      return MathSqrt(sum);
   }

   double RangeBps(const VxCompletedFeatureWindow &w[],const int first,const int last) const
   {
      if(first<0 || last>=ArraySize(w) || first>last) return -1.0;
      double hi=w[first].mid_high,lo=w[first].mid_low,base=w[first].mid_close;
      if(base<=0.0) return -1.0;
      for(int i=first+1;i<=last;i++)
      { hi=MathMax(hi,w[i].mid_high);lo=MathMin(lo,w[i].mid_low); }
      return (hi-lo)/base*10000.0;
   }

   double Percentile(double &values[],const double fraction) const
   {
      int n=ArraySize(values);
      if(n<=0 || fraction<0.0 || fraction>1.0) return -1.0;
      double sorted[];
      ArrayResize(sorted,n);
      ArrayCopy(sorted,values);
      ArraySort(sorted);
      double index=(n-1)*fraction;
      int lo=(int)MathFloor(index),hi=(int)MathCeil(index);
      if(lo==hi) return sorted[lo];
      return sorted[lo]+(sorted[hi]-sorted[lo])*(index-lo);
   }

   void Append(const string candidate,const int direction,const long end_msc,
               const int horizon,const int lookback,const double threshold,
               const double compression,const double score,
               VxResearchSignal &signals[],int &count) const
   {
      int n=ArrayResize(signals,count+1);
      if(n!=count+1) return;
      signals[count].candidate_id=candidate;
      signals[count].direction=direction;
      signals[count].signal_window_end_msc=end_msc;
      signals[count].horizon_seconds=horizon;
      signals[count].lookback_seconds=lookback;
      signals[count].threshold=threshold;
      signals[count].compression_percentile=compression;
      signals[count].standardized_score=score;
      signals[count].research_only=true;
      count++;
   }

public:
   bool EvaluateLatest(const VxCompletedFeatureWindow &windows[],
                       VxResearchSignal &signals[],int &signal_count,
                       string &reason) const
   {
      signal_count=0;
      ArrayResize(signals,0);
      int count=ArraySize(windows);
      if(count<2){reason="Insufficient completed XAUUSD windows";return false;}
      for(int i=0;i<count;i++)
      {
         if(!ValidWindow(windows[i]))
         { reason="Feature history contains invalid, incomplete, or non-XAUUSD window";return false; }
         if(i>0 && windows[i].start_msc<=windows[i-1].start_msc)
         { reason="Feature history is not strictly chronological";return false; }
      }

      int current=count-1;
      long end_msc=windows[current].start_msc+VX_CANDIDATE_WINDOW_MS;
      double close=windows[current].mid_close;
      int horizons[4]={5,15,30,60};
      int momentum_lookbacks[3]={5,10,15};
      double momentum_thresholds[3]={0.5,1.0,1.5};

      // Momentum continuation: current close versus L seconds earlier;
      // volatility uses only the L/5 preceding completed windows.
      for(int a=0;a<3;a++)
      {
         int n=momentum_lookbacks[a]/5,first=current-n;
         if(first<0 || !Consecutive(windows,first,current)) continue;
         double scale=Scale(windows,first,current-1);
         if(scale<=0.0) continue;
         double z=10000.0*MathLog(close/windows[first].mid_close)/scale;
         for(int b=0;b<3;b++)
            if(MathAbs(z)>=momentum_thresholds[b])
               for(int h=0;h<4;h++)
                  Append("XAU_MOMENTUM_CONTINUATION_V1",(z>0.0?1:-1),end_msc,
                         horizons[h],momentum_lookbacks[a],momentum_thresholds[b],0.0,z,
                         signals,signal_count);
      }

      // Mean reversion: arithmetic reference mean from strictly prior closes.
      int mean_lookbacks[3]={15,30,60};
      double mean_thresholds[3]={1.0,1.5,2.0};
      for(int a=0;a<3;a++)
      {
         int n=mean_lookbacks[a]/5,first=current-n;
         if(first<0 || !Consecutive(windows,first,current)) continue;
         double scale=Scale(windows,first,current-1),reference=0.0;
         if(scale<=0.0) continue;
         for(int j=first;j<current;j++) reference+=windows[j].mid_close;
         reference/=n;
         if(reference<=0.0) continue;
         double z=10000.0*MathLog(close/reference)/scale;
         for(int b=0;b<3;b++)
            if(MathAbs(z)>=mean_thresholds[b])
               for(int h=0;h<4;h++)
                  Append("XAU_MEAN_REVERSION_V1",(z>0.0?-1:1),end_msc,
                         horizons[h],mean_lookbacks[a],mean_thresholds[b],0.0,z,
                         signals,signal_count);
      }

      // Volatility breakout: prior range and 60 prior rolling ranges.
      int breakout_lookbacks[2]={30,60};
      double distance_fractions[3]={0.25,0.5,1.0};
      double compression_percentiles[2]={25.0,35.0};
      for(int a=0;a<2;a++)
      {
         int n=breakout_lookbacks[a]/5,first=current-n;
         int compression_first=current-VX_CANDIDATE_HISTORY;
         if(first<0 || compression_first-n<0 ||
            !Consecutive(windows,compression_first-n,current)) continue;
         double scale=Scale(windows,first,current-1);
         if(scale<=0.0) continue;
         double prior_high=windows[first].mid_high,prior_low=windows[first].mid_low;
         for(int j=first+1;j<current;j++)
         { prior_high=MathMax(prior_high,windows[j].mid_high);prior_low=MathMin(prior_low,windows[j].mid_low); }
         double current_range=(prior_high-prior_low)/windows[first].mid_close*10000.0;
         double history[];
         ArrayResize(history,VX_CANDIDATE_HISTORY);
         bool valid=true;
         for(int k=0;k<VX_CANDIDATE_HISTORY;k++)
         {
            int j=current-VX_CANDIDATE_HISTORY+k;
            int range_first=j-n;
            if(range_first<0 || !Consecutive(windows,range_first,j)) {valid=false;break;}
            history[k]=RangeBps(windows,range_first,j-1);
            if(history[k]<0.0) {valid=false;break;}
         }
         if(!valid) continue;
         double up=(close>prior_high?10000.0*MathLog(close/prior_high):0.0);
         double down=(close<prior_low?10000.0*MathLog(prior_low/close):0.0);
         for(int p=0;p<2;p++)
         {
            double limit=Percentile(history,compression_percentiles[p]/100.0);
            if(limit<0.0 || current_range>limit) continue;
            for(int d=0;d<3;d++)
            {
               double threshold=distance_fractions[d],score=0.0;
               int direction=0;
               if(up>=threshold*scale) {direction=1;score=up/scale;}
               else if(down>=threshold*scale) {direction=-1;score=down/scale;}
               if(direction==0) continue;
               for(int h=0;h<4;h++)
                  Append("XAU_VOLATILITY_BREAKOUT_V1",direction,end_msc,
                         horizons[h],breakout_lookbacks[a],threshold,
                         compression_percentiles[p],score,signals,signal_count);
            }
         }
      }
      reason="";
      return true;
   }
};

#endif
