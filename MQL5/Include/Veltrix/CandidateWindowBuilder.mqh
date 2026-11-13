//+------------------------------------------------------------------+
//| CandidateWindowBuilder.mqh                                       |
//| Builds completed UTC five-second windows from fresh XAUUSD ticks|
//| Read-only analysis adapter.                                      |
//+------------------------------------------------------------------+
#ifndef VELTRIX_CANDIDATE_WINDOW_BUILDER_MQH
#define VELTRIX_CANDIDATE_WINDOW_BUILDER_MQH

#include "CandidateAnalysis.mqh"

class CVxCandidateWindowBuilder
{
private:
   string m_broker_symbol;
   int m_capacity;
   VxCompletedFeatureWindow m_history[];
   VxCompletedFeatureWindow m_current;
   long m_current_start_msc;
   long m_last_tick_msc;
   double m_previous_mid;
   double m_sum_squared_log_returns;
   int m_observations;
   bool m_initialized;
   bool m_faulted;
   string m_fault_reason;

   bool VerifiedXauContract(const string symbol) const
   {
      string normalized=symbol;
      StringToUpper(normalized);
      if(StringLen(normalized)<6 || StringSubstr(normalized,0,6)!="XAUUSD")
         return false;
      string base="",profit="";
      if(!SymbolInfoString(symbol,SYMBOL_CURRENCY_BASE,base) ||
         !SymbolInfoString(symbol,SYMBOL_CURRENCY_PROFIT,profit))
         return false;
      StringToUpper(base);
      StringToUpper(profit);
      return (base=="XAU" && profit=="USD");
   }

   void StartWindow(const long start_msc,const double mid)
   {
      m_current.symbol="XAUUSD";
      m_current.start_msc=start_msc;
      m_current.window_seconds=5;
      m_current.completed=false;
      m_current.mid_close=mid;
      m_current.mid_high=mid;
      m_current.mid_low=mid;
      m_current.realized_volatility_bps=0.0;
      m_current.valid=false;
      m_current_start_msc=start_msc;
      m_previous_mid=mid;
      m_sum_squared_log_returns=0.0;
      m_observations=1;
   }

   bool FinalizeCurrent(string &reason)
   {
      m_current.completed=true;
      if(m_observations<2)
      {
         m_current.valid=false;
         m_current.realized_volatility_bps=0.0;
      }
      else
      {
         m_current.realized_volatility_bps=MathSqrt(m_sum_squared_log_returns)*10000.0;
         m_current.valid=MathIsValidNumber(m_current.realized_volatility_bps) &&
                          m_current.realized_volatility_bps>=0.0;
      }
      int count=ArraySize(m_history);
      if(count>=m_capacity)
      {
         for(int i=1;i<count;i++) m_history[i-1]=m_history[i];
         count--;
         if(ArrayResize(m_history,count)!=count)
         { reason="Unable to shift completed-window history"; return false; }
      }
      if(ArrayResize(m_history,count+1)!=count+1)
      { reason="Unable to append completed feature window"; return false; }
      m_history[count]=m_current;
      reason="";
      return true;
   }

public:
   CVxCandidateWindowBuilder()
   {
      m_broker_symbol="";
      m_capacity=0;
      m_current_start_msc=0;
      m_last_tick_msc=0;
      m_previous_mid=0.0;
      m_sum_squared_log_returns=0.0;
      m_observations=0;
      m_initialized=false;
      m_faulted=false;
      m_fault_reason="";
   }

   bool Init(const string broker_symbol,const int capacity,string &reason)
   {
      m_initialized=false;
      m_faulted=false;
      m_fault_reason="";
      if(!VerifiedXauContract(broker_symbol) || capacity<80 || capacity>100000)
      { reason="Candidate window builder requires verified XAUUSD and capacity >= 80"; return false; }
      ArrayResize(m_history,0);
      m_broker_symbol=broker_symbol;
      m_capacity=capacity;
      m_current_start_msc=0;
      m_last_tick_msc=0;
      m_observations=0;
      m_initialized=true;
      reason="";
      return true;
   }

   bool PushQuote(const string broker_symbol,const MqlTick &tick,
                  bool &window_completed,string &reason)
   {
      window_completed=false;
      reason="";
      if(!m_initialized || m_faulted)
      { reason=(m_faulted ? m_fault_reason : "Candidate window builder is not initialized"); return false; }
      if(broker_symbol!=m_broker_symbol || !VerifiedXauContract(broker_symbol))
      { reason="Candidate window builder accepts only its verified XAUUSD broker contract"; m_faulted=true; m_fault_reason=reason; return false; }
      if(tick.time_msc<=0 || !MathIsValidNumber(tick.bid) ||
         !MathIsValidNumber(tick.ask) || tick.bid<=0.0 || tick.ask<=tick.bid)
      { reason="Candidate builder received an invalid bid/ask quote"; m_faulted=true; m_fault_reason=reason; return false; }
      if(tick.time_msc<m_last_tick_msc)
      { reason="Candidate builder received an out-of-order quote"; m_faulted=true; m_fault_reason=reason; return false; }
      if(tick.time_msc==m_last_tick_msc)
         return true;
      m_last_tick_msc=tick.time_msc;

      double mid=(tick.bid+tick.ask)/2.0;
      if(!MathIsValidNumber(mid) || mid<=0.0)
      { reason="Candidate builder midpoint is invalid"; m_faulted=true; m_fault_reason=reason; return false; }
      long bucket=(tick.time_msc/5000)*5000;
      if(m_current_start_msc==0)
      {
         StartWindow(bucket,mid);
         return true;
      }
      if(bucket<m_current_start_msc)
      { reason="Candidate builder bucket moved backwards"; m_faulted=true; m_fault_reason=reason; return false; }
      if(bucket==m_current_start_msc)
      {
         double lr=MathLog(mid/m_previous_mid);
         if(!MathIsValidNumber(lr))
         { reason="Candidate builder log return is invalid"; m_faulted=true; m_fault_reason=reason; return false; }
         m_sum_squared_log_returns+=lr*lr;
         if(!MathIsValidNumber(m_sum_squared_log_returns))
         { reason="Candidate builder volatility accumulation is invalid"; m_faulted=true; m_fault_reason=reason; return false; }
         m_current.mid_high=MathMax(m_current.mid_high,mid);
         m_current.mid_low=MathMin(m_current.mid_low,mid);
         m_current.mid_close=mid;
         m_previous_mid=mid;
         m_observations++;
         return true;
      }

      if(!FinalizeCurrent(reason))
      { m_faulted=true; m_fault_reason=reason; return false; }
      window_completed=true;
      StartWindow(bucket,mid);
      return true;
   }

   bool CopyCompletedWindows(VxCompletedFeatureWindow &out[]) const
   {
      int count=ArraySize(m_history);
      if(count<=0 || ArrayResize(out,count)!=count)
         return false;
      ArrayCopy(out,m_history,0,0,count);
      return true;
   }

   int Count(void) const { return ArraySize(m_history); }
   bool IsFaulted(void) const { return m_faulted; }
   string FaultReason(void) const { return m_fault_reason; }
};

#endif
