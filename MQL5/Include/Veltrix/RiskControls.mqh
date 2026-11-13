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
   string m_emergency_key;
   string m_day_key_name;
   string m_day_equity_name;
   string m_daily_lock_name;
   string m_loss_streak_name;
   string m_cooldown_name;
   string m_state_checksum_name;

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

   ulong ServerHash(const string value) const
   {
      // FNV-1a 64-bit; unsigned overflow is intentional and deterministic.
      ulong hash=14695981039346656037;
      for(int i=0;i<StringLen(value);i++)
      {
         hash^=(ulong)StringGetCharacter(value,i);
         hash*=1099511628211;
      }
      return hash;
   }

   string RequestKey(const string request_id) const
   {
      return StringFormat("VX_REQ_%I64d_%I64u_%I64u",
                          m_config.expected_demo_login,
                          ServerHash(m_config.expected_demo_server),
                          ServerHash(request_id));
   }

   double RiskStateChecksum(void) const
   {
      string serialized=StringFormat("%d|%I64d|%.17g|%d|%I64d|%I64d",
                                     (m_emergency_stop ? 1 : 0),
                                     m_server_day_key,m_day_start_equity,
                                     (m_daily_loss_locked ? 1 : 0),
                                     m_consecutive_losses,m_cooldown_until_msc);
      return (double)(ServerHash(serialized)%9007199254740991);
   }

   bool PersistRiskState(void)
   {
      if(m_emergency_key=="" || m_day_key_name=="" ||
         m_day_equity_name=="" || m_daily_lock_name=="" ||
         m_loss_streak_name=="" || m_cooldown_name=="" ||
         m_state_checksum_name=="")
         return false;
      if(GlobalVariableSet(m_emergency_key,(m_emergency_stop ? 1.0 : 0.0))==0 ||
         GlobalVariableSet(m_day_key_name,(double)m_server_day_key)==0 ||
         GlobalVariableSet(m_day_equity_name,m_day_start_equity)==0 ||
         GlobalVariableSet(m_daily_lock_name,(m_daily_loss_locked ? 1.0 : 0.0))==0 ||
         GlobalVariableSet(m_loss_streak_name,(double)m_consecutive_losses)==0 ||
         GlobalVariableSet(m_cooldown_name,(double)m_cooldown_until_msc)==0)
         return false;
      // Commit marker is written last. A crash or partial write is detected
      // as a checksum mismatch on the next initialization.
      if(GlobalVariableSet(m_state_checksum_name,RiskStateChecksum())==0)
         return false;
      GlobalVariablesFlush();
      return true;
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
      m_emergency_key="";
      m_day_key_name="";
      m_day_equity_name="";
      m_daily_lock_name="";
      m_loss_streak_name="";
      m_cooldown_name="";
      m_state_checksum_name="";
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
      string suffix=StringFormat("%I64d_%I64u",
                                 config.expected_demo_login,
                                 ServerHash(config.expected_demo_server));
      m_emergency_key="VX_ESTOP_"+suffix;
      m_day_key_name="VX_DAY_"+suffix;
      m_day_equity_name="VX_EQ_"+suffix;
      m_daily_lock_name="VX_LOCK_"+suffix;
      m_loss_streak_name="VX_LS_"+suffix;
      m_cooldown_name="VX_CD_"+suffix;
      m_state_checksum_name="VX_CSUM_"+suffix;
      if(StringLen(m_emergency_key)>63 || StringLen(m_day_key_name)>63 ||
         StringLen(m_day_equity_name)>63 || StringLen(m_daily_lock_name)>63 ||
         StringLen(m_loss_streak_name)>63 || StringLen(m_cooldown_name)>63 ||
         StringLen(m_state_checksum_name)>63)
      { reason="Risk-state persistence key is invalid"; return false; }

      string keys[7];
      keys[0]=m_emergency_key; keys[1]=m_day_key_name;
      keys[2]=m_day_equity_name; keys[3]=m_daily_lock_name;
      keys[4]=m_loss_streak_name; keys[5]=m_cooldown_name;
      keys[6]=m_state_checksum_name;
      int present=0;
      for(int i=0;i<7;i++)
         if(GlobalVariableCheck(keys[i])) present++;
      if(present!=0 && present!=7)
      { reason="Persistent risk state is incomplete; refusing to reset partial state"; return false; }
      if(present==0)
      {
         if(!PersistRiskState())
         { reason="Could not initialize persistent risk state"; return false; }
      }
      else
      {
         double emergency=GlobalVariableGet(m_emergency_key);
         double day=GlobalVariableGet(m_day_key_name);
         double equity=GlobalVariableGet(m_day_equity_name);
         double daily_lock=GlobalVariableGet(m_daily_lock_name);
         double losses=GlobalVariableGet(m_loss_streak_name);
         double cooldown=GlobalVariableGet(m_cooldown_name);
         if(!MathIsValidNumber(emergency) || !MathIsValidNumber(day) ||
            !MathIsValidNumber(equity) || !MathIsValidNumber(daily_lock) ||
            !MathIsValidNumber(losses) || !MathIsValidNumber(cooldown) ||
            (emergency!=0.0 && emergency!=1.0) ||
            (daily_lock!=0.0 && daily_lock!=1.0) ||
            day<0.0 || equity<0.0 || losses<0.0 || losses>3.0 ||
            MathFloor(losses)!=losses || cooldown<0.0)
         { reason="Persistent risk state is corrupt; refusing initialization"; return false; }
         m_emergency_stop=(emergency>0.5);
         m_server_day_key=(long)day;
         m_day_start_equity=equity;
         m_daily_loss_locked=(daily_lock>0.5);
         m_consecutive_losses=(int)losses;
         m_cooldown_until_msc=(long)cooldown;
         double stored_checksum=GlobalVariableGet(m_state_checksum_name);
         if(!MathIsValidNumber(stored_checksum) ||
            stored_checksum!=RiskStateChecksum())
         { reason="Persistent risk-state checksum mismatch; refusing initialization"; return false; }
         if(m_consecutive_losses>=m_config.max_consecutive_losses)
            m_daily_loss_locked=true;
      }
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
      if(!VerifyExactDemoAccount(reason))
         return false;
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
      if(!PersistRiskState())
      {
         m_emergency_stop=true;
         PersistRiskState();
         reason="Could not persist new server-day risk baseline; emergency stop latched";
         return false;
      }
      return true;
   }

   bool EvaluateDailyLoss(const double current_equity,string &reason)
   {
      reason="";
      if(!m_initialized || m_server_day_key<=0 || m_day_start_equity<=0.0 ||
         !MathIsValidNumber(current_equity) || current_equity<=0.0)
      { reason="Daily equity baseline or current equity is unavailable"; return false; }
      if(!VerifyExactDemoAccount(reason))
         return false;
      if(m_daily_loss_locked)
      { reason="Daily loss lock is latched until the next verified server day"; return false; }
      double loss_percent=(m_day_start_equity-current_equity)/m_day_start_equity*100.0;
      if(!MathIsValidNumber(loss_percent))
      { reason="Daily loss calculation is non-finite"; return false; }
      if(loss_percent>=m_config.max_daily_loss_percent)
      {
         m_daily_loss_locked=true;
         if(!PersistRiskState())
         {
            m_emergency_stop=true;
            PersistRiskState();
            reason="Daily loss reached and risk-state persistence failed; emergency stop latched";
            return false;
         }
         reason="Maximum daily equity loss reached; new intents locked until next server day";
         return false;
      }
      return true;
   }

   bool RecordVerifiedClose(const ulong closing_deal_ticket,const double net_profit,
                            const long close_time_msc,string &reason)
   {
      reason="";
      if(!m_initialized || closing_deal_ticket==0 ||
         !MathIsValidNumber(net_profit) || close_time_msc<=0)
      { reason="Only a unique verified closing deal with finite net P/L and valid time may update loss controls"; return false; }
      if(!VerifyExactDemoAccount(reason))
         return false;
      string close_key=StringFormat("VX_CLOSE_%I64d_%I64u_%I64u",
                                    m_config.expected_demo_login,
                                    ServerHash(m_config.expected_demo_server),
                                    ServerHash(StringFormat("%I64u",closing_deal_ticket)));
      if(close_key=="" || StringLen(close_key)>63)
      { reason="Closing-deal deduplication key is invalid"; return false; }
      if(GlobalVariableCheck(close_key))
      { reason="Duplicate verified closing deal ignored"; return false; }
      if(net_profit<0.0)
      {
         m_consecutive_losses++;
         m_cooldown_until_msc=close_time_msc+(long)m_config.cooldown_seconds*1000;
         if(m_consecutive_losses>=m_config.max_consecutive_losses)
         {
            m_daily_loss_locked=true;
            reason="Consecutive-loss limit reached; daily lock latched";
         }
      }
      else if(net_profit>0.0)
      {
         m_consecutive_losses=0;
      }
      if(!PersistRiskState())
      {
         m_emergency_stop=true;
         PersistRiskState();
         reason="Could not persist verified close risk state; emergency stop latched";
         return false;
      }
      if(GlobalVariableSet(close_key,1.0)==0)
      {
         m_emergency_stop=true;
         PersistRiskState();
         reason="Could not persist closing-deal deduplication; emergency stop latched";
         return false;
      }
      GlobalVariablesFlush();
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
      if(m_cooldown_until_msc>0 && now_msc<m_cooldown_until_msc)
      { reason="Post-loss cooldown is active"; return false; }
      string request_key=RequestKey(request_id);
      if(request_key=="" || StringLen(request_key)>63)
      { reason="Request deduplication key is invalid"; return false; }
      if(GlobalVariableCheck(request_key))
      { reason="Duplicate request identifier rejected"; return false; }
      if(GlobalVariableSet(request_key,(double)now_msc)==0)
      { reason="Could not persist request deduplication state; fail closed"; return false; }
      GlobalVariablesFlush();
      return true;
   }

   bool LatchEmergencyStop(string &reason)
   {
      reason="";
      m_emergency_stop=true;
      if(!m_initialized || !PersistRiskState())
      { reason="Emergency stop latched in memory but persistent risk-state write failed"; return false; }
      return true;
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
