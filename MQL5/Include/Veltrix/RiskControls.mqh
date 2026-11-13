//+------------------------------------------------------------------+
//| RiskControls.mqh                                                 |
//| XAUUSD-only DEMO risk policy and lockout state.                   |
//| This module approves local research intents only; no order APIs.  |
//+------------------------------------------------------------------+
#ifndef VELTRIX_RISK_CONTROLS_MQH
#define VELTRIX_RISK_CONTROLS_MQH

#include "RiskAllocator.mqh"

struct VxRiskControlConfig
{
   long   expected_demo_login;
   string expected_demo_server;
   double risk_per_trade_percent;
   double max_portfolio_risk_percent;
   double max_daily_loss_percent;
   int    max_positions;
   int    cooldown_seconds;
   int    max_consecutive_losses;
};

class CVxRiskControls
{
private:
   VxRiskControlConfig m_config;
   bool m_initialized;
   bool m_emergency_stop;
   bool m_daily_loss_locked;
   long m_server_day_key;
   double m_day_start_equity;
   int m_consecutive_losses;
   long m_cooldown_until_msc;
   string m_seen_request_ids[];

   bool IsXauUsdContract(const string symbol)
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

   bool RequestSeen(const string request_id) const
   {
      for(int i=0;i<ArraySize(m_seen_request_ids);i++)
         if(m_seen_request_ids[i]==request_id)
            return true;
      return false;
   }

public:
   CVxRiskControls(void)
   {
      m_initialized=false;
      m_emergency_stop=false;
      m_daily_loss_locked=false;
      m_server_day_key=0;
      m_day_start_equity=0.0;
      m_consecutive_losses=0;
      m_cooldown_until_msc=0;
   }

   bool Init(const VxRiskControlConfig &config,string &reason)
   {
      reason="";
      m_initialized=false;
      if(config.expected_demo_login<=0 || config.expected_demo_server=="")
      { reason="Exact expected DEMO login and server are mandatory"; return false; }
      if(!MathIsValidNumber(config.risk_per_trade_percent) ||
         !MathIsValidNumber(config.max_portfolio_risk_percent) ||
         !MathIsValidNumber(config.max_daily_loss_percent))
      { reason="Risk percentages must be finite"; return false; }
      // Conservative hard ceilings are policy limits, not suggested targets.
      if(config.risk_per_trade_percent<=0.0 ||
         config.risk_per_trade_percent>0.25 ||
         config.max_portfolio_risk_percent<=0.0 ||
         config.max_portfolio_risk_percent>0.50 ||
         config.max_daily_loss_percent<=0.0 ||
         config.max_daily_loss_percent>1.00)
      { reason="Risk configuration exceeds hard policy ceilings"; return false; }
      if(config.max_positions!=1 ||
         config.cooldown_seconds<30 || config.cooldown_seconds>3600 ||
         config.max_consecutive_losses<1 || config.max_consecutive_losses>3)
      { reason="Policy requires one position, 30-3600s cooldown, and 1-3 consecutive-loss limit"; return false; }

      m_config=config;
      m_initialized=true;
      return true;
   }

   bool VerifyExactDemoAccount(string &reason) const
   {
      reason="";
      if(!m_initialized)
      { reason="Risk controls are not initialized"; return false; }
      if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
      { reason="Account is not DEMO"; return false; }
      if((long)AccountInfoInteger(ACCOUNT_LOGIN)!=m_config.expected_demo_login)
      { reason="Connected account login does not match configured DEMO login"; return false; }
      if(AccountInfoString(ACCOUNT_SERVER)!=m_config.expected_demo_server)
      { reason="Connected broker server does not exactly match configured DEMO server"; return false; }
      if(!TerminalInfoInteger(TERMINAL_CONNECTED))
      { reason="Terminal is disconnected"; return false; }
      return true;
   }

   bool BeginServerDay(const long day_key,const double starting_equity,string &reason)
   {
      reason="";
      if(!m_initialized || day_key<=0 ||
         !MathIsValidNumber(starting_equity) || starting_equity<=0.0)
      { reason="Invalid risk state, server-day key, or starting equity"; return false; }
      if(m_server_day_key>0 && day_key<m_server_day_key)
      { reason="Server-day key moved backwards; refusing to reset risk state"; return false; }
      if(day_key==m_server_day_key)
      {
         if(MathAbs(starting_equity-m_day_start_equity)>MathMax(0.01,m_day_start_equity*1e-8))
         { reason="Starting equity cannot be silently replaced within the same server day"; return false; }
         return true;
      }
      m_server_day_key=day_key;
      m_day_start_equity=starting_equity;
      m_daily_loss_locked=false;
      m_consecutive_losses=0;
      // A cooldown and emergency stop deliberately survive a day boundary.
      return true;
   }

   bool EvaluateDailyLoss(const double current_equity,string &reason)
   {
      reason="";
      if(!m_initialized || m_server_day_key<=0 || m_day_start_equity<=0.0 ||
         !MathIsValidNumber(current_equity) || current_equity<=0.0)
      { reason="Daily equity baseline or current equity is unavailable"; return false; }
      if(m_daily_loss_locked)
      { reason="Daily loss lock is latched until the next verified server day"; return false; }
      double loss_percent=(m_day_start_equity-current_equity)/m_day_start_equity*100.0;
      if(!MathIsValidNumber(loss_percent))
      { reason="Daily loss calculation is non-finite"; return false; }
      if(loss_percent>=m_config.max_daily_loss_percent)
      {
         m_daily_loss_locked=true;
         reason="Maximum daily equity loss reached; new intents locked until next server day";
         return false;
      }
      return true;
   }

   bool RecordVerifiedClose(const double net_profit,const long close_time_msc,string &reason)
   {
      reason="";
      if(!m_initialized || !MathIsValidNumber(net_profit) || close_time_msc<=0)
      { reason="Only a verified close with finite net P/L and valid time may update loss controls"; return false; }
      if(net_profit<0.0)
      {
         m_consecutive_losses++;
         m_cooldown_until_msc=close_time_msc+(long)m_config.cooldown_seconds*1000;
         if(m_consecutive_losses>=m_config.max_consecutive_losses)
         {
            m_daily_loss_locked=true;
            reason="Consecutive-loss limit reached; daily lock latched";
            return true;
         }
      }
      else if(net_profit>0.0)
      {
         m_consecutive_losses=0;
      }
      return true;
   }

   bool CalculateVolume(const VxRiskRequest &source,const int active_positions,
                        VxRiskDecision &decision)
   {
      decision.approved=false;
      decision.volume=0.0;
      decision.risk_budget_money=0.0;
      decision.portfolio_capacity_money=0.0;
      decision.estimated_loss_money=0.0;
      decision.reason="";
      if(!m_initialized || m_emergency_stop || m_daily_loss_locked)
      { decision.reason="Risk controls are uninitialized or locked"; return false; }
      string guard_reason;
      if(!VerifyExactDemoAccount(guard_reason))
      { decision.reason=guard_reason; return false; }
      if(!EvaluateDailyLoss(source.equity,guard_reason))
      { decision.reason=guard_reason; return false; }
      VxRiskRequest request=source;
      request.risk_percent=m_config.risk_per_trade_percent;
      request.max_portfolio_risk_percent=m_config.max_portfolio_risk_percent;
      request.open_positions=active_positions;
      request.max_positions=m_config.max_positions;
      return VxCalculateRiskVolume(request,decision);
   }

   bool RegisterApprovedIntent(const string request_id,const string symbol,
                               const int active_positions,const double current_equity,
                               const long now_msc,string &reason)
   {
      reason="";
      if(!m_initialized || m_emergency_stop || m_daily_loss_locked)
      { reason="Risk controls are uninitialized or locked"; return false; }
      if(!VerifyExactDemoAccount(reason))
         return false;
      if(!EvaluateDailyLoss(current_equity,reason))
         return false;
      if(request_id=="" || now_msc<=0 || active_positions<0)
      { reason="Invalid request identity, timestamp, or position count"; return false; }
      if(!IsXauUsdContract(symbol))
      { reason="Only a verified XAUUSD contract is permitted"; return false; }
      if(active_positions>=m_config.max_positions)
      { reason="Maximum simultaneous position exposure reached"; return false; }
      if(RequestSeen(request_id))
      { reason="Duplicate request identifier rejected"; return false; }
      if(m_cooldown_until_msc>0 && now_msc<m_cooldown_until_msc)
      { reason="Post-loss cooldown is active"; return false; }
      if(ArraySize(m_seen_request_ids)>=10000)
      { reason="Request deduplication capacity exhausted; fail closed"; return false; }
      int size=ArraySize(m_seen_request_ids);
      if(ArrayResize(m_seen_request_ids,size+1)!=size+1)
      { reason="Request deduplication allocation failed"; return false; }
      m_seen_request_ids[size]=request_id;
      return true;
   }

   void LatchEmergencyStop(void)
   {
      m_emergency_stop=true;
   }

   bool IsLocked(void) const
   {
      return (!m_initialized || m_emergency_stop || m_daily_loss_locked);
   }

   bool IsEmergencyStopped(void) const { return m_emergency_stop; }
   bool IsDailyLossLocked(void) const { return m_daily_loss_locked; }
   int ConsecutiveLosses(void) const { return m_consecutive_losses; }
   long CooldownUntilMsc(void) const { return m_cooldown_until_msc; }
   long ServerDayKey(void) const { return m_server_day_key; }
};

#endif
