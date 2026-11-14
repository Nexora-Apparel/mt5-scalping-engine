//+------------------------------------------------------------------+
//| OverallAccountLossGuard.mqh                                      |
//| Persistent 50% original-deposit loss ceiling; no order APIs.     |
//+------------------------------------------------------------------+
#ifndef VELTRIX_OVERALL_ACCOUNT_LOSS_GUARD_MQH
#define VELTRIX_OVERALL_ACCOUNT_LOSS_GUARD_MQH

class CVxOverallAccountLossGuard
{
private:
   long m_expected_login;
   string m_expected_server;
   double m_original_deposit;
   double m_loss_limit_percent;
   bool m_locked;
   bool m_initialized;
   string m_baseline_key;
   string m_lock_key;
   string m_checksum_key;

   ulong Hash64(const string value) const
   {
      ulong hash=14695981039346656037;
      for(int i=0;i<StringLen(value);i++)
      {
         hash^=(ulong)StringGetCharacter(value,i);
         hash*=1099511628211;
      }
      return hash;
   }

   string AccountSuffix(const long login,const string server) const
   {
      return StringFormat("%I64d_%I64u",login,Hash64(server));
   }

   double StateChecksum(const double baseline,const bool locked) const
   {
      string payload=StringFormat("%I64d|%s|%.17g|%.8f|%d",
                                 m_expected_login,m_expected_server,
                                 baseline,m_loss_limit_percent,
                                 (locked ? 1 : 0));
      return (double)(Hash64(payload)%9007199254740991);
   }

   bool Persist(void)
   {
      if(m_baseline_key=="" || m_lock_key=="" || m_checksum_key=="")
         return false;
      if(GlobalVariableSet(m_baseline_key,m_original_deposit)==0 ||
         GlobalVariableSet(m_lock_key,(m_locked ? 1.0 : 0.0))==0 ||
         GlobalVariableSet(m_checksum_key,
                           StateChecksum(m_original_deposit,m_locked))==0)
         return false;
      GlobalVariablesFlush();
      return true;
   }

   bool VerifyAccount(string &reason) const
   {
      reason="";
      if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
      { reason="Overall-loss guard requires a DEMO account"; return false; }
      if((long)AccountInfoInteger(ACCOUNT_LOGIN)!=m_expected_login)
      { reason="Connected account login differs from the configured DEMO identity"; return false; }
      if(AccountInfoString(ACCOUNT_SERVER)!=m_expected_server)
      { reason="Connected server differs from the configured DEMO identity"; return false; }
      if(!TerminalInfoInteger(TERMINAL_CONNECTED))
      { reason="Terminal is disconnected"; return false; }
      return true;
   }

public:
   CVxOverallAccountLossGuard(void)
   {
      m_expected_login=0;
      m_expected_server="";
      m_original_deposit=0.0;
      m_loss_limit_percent=50.0;
      m_locked=false;
      m_initialized=false;
      m_baseline_key="";
      m_lock_key="";
      m_checksum_key="";
   }

   // original_deposit_verified must come from an owner-reviewed broker
   // statement/deposit record. This method never infers it from current balance.
   bool Init(const long expected_demo_login,const string expected_demo_server,
             const double verified_original_deposit,
             const bool original_deposit_verified,string &reason)
   {
      reason="";
      m_initialized=false;
      if(expected_demo_login<=0 || expected_demo_server=="" ||
         !original_deposit_verified ||
         !MathIsValidNumber(verified_original_deposit) ||
         verified_original_deposit<=0.0)
      { reason="An exact DEMO identity and independently owner-verified original deposit are mandatory"; return false; }

      m_expected_login=expected_demo_login;
      m_expected_server=expected_demo_server;
      m_baseline_key="VX_ORIGDEP_"+AccountSuffix(expected_demo_login,expected_demo_server);
      m_lock_key="VX_OVERALL_LOCK_"+AccountSuffix(expected_demo_login,expected_demo_server);
      m_checksum_key="VX_OVERALL_SUM_"+AccountSuffix(expected_demo_login,expected_demo_server);
      if(StringLen(m_baseline_key)>63 || StringLen(m_lock_key)>63 ||
         StringLen(m_checksum_key)>63)
      { reason="Overall-loss persistence key exceeds terminal limits"; return false; }

      bool has_baseline=GlobalVariableCheck(m_baseline_key);
      bool has_lock=GlobalVariableCheck(m_lock_key);
      bool has_checksum=GlobalVariableCheck(m_checksum_key);
      if(!has_baseline && !has_lock && !has_checksum)
      {
         m_original_deposit=verified_original_deposit;
         m_locked=false;
         if(!Persist())
         { reason="Could not persist immutable original-deposit baseline"; return false; }
      }
      else
      {
         if(!has_baseline || !has_lock || !has_checksum)
         { reason="Overall-loss persistent state is partial; refusing automatic repair"; return false; }
         double stored_baseline=GlobalVariableGet(m_baseline_key);
         double stored_lock=GlobalVariableGet(m_lock_key);
         double stored_checksum=GlobalVariableGet(m_checksum_key);
         if(!MathIsValidNumber(stored_baseline) || stored_baseline<=0.0 ||
            !MathIsValidNumber(stored_lock) || (stored_lock!=0.0 && stored_lock!=1.0) ||
            !MathIsValidNumber(stored_checksum))
         { reason="Overall-loss persistent state is corrupt"; return false; }
         if(MathAbs(stored_baseline-verified_original_deposit)>
            MathMax(0.01,verified_original_deposit*1e-8))
         { reason="Supplied original-deposit evidence conflicts with the immutable stored baseline"; return false; }
         m_original_deposit=stored_baseline;
         m_locked=(stored_lock>0.5);
         if(stored_checksum!=StateChecksum(m_original_deposit,m_locked))
         { reason="Overall-loss persistent checksum mismatch; refusing initialization"; return false; }
      }
      // Broker identity and live equity are checked on every evaluation, not at init;
      // this also permits offline synthetic persistence/restart tests.
      m_initialized=true;
      return true;
   }

   // Account equity includes floating P/L; broker-booked commissions and swaps
   // reflected in account equity are therefore included in the loss calculation.
   bool Evaluate(string &reason)
   {
      reason="";
      if(!m_initialized)
      { reason="Overall-loss guard is not initialized"; return false; }
      if(!VerifyAccount(reason)) return false;
      if(m_locked)
      { reason="50% original-deposit loss ceiling is latched pending owner reactivation"; return false; }
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      if(!MathIsValidNumber(equity) || equity<=0.0)
      { reason="Current account equity is unavailable or invalid"; return false; }
      double loss_percent=(m_original_deposit-equity)/m_original_deposit*100.0;
      if(!MathIsValidNumber(loss_percent))
      { reason="Overall account-loss calculation is non-finite"; return false; }
      if(loss_percent>=m_loss_limit_percent)
      {
         m_locked=true;
         if(!Persist())
         { reason="50% overall-loss threshold reached but durable lock persistence failed; fail closed"; return false; }
         reason="50% original-deposit account-loss ceiling reached; reactivation requires trusted owner control";
         return false;
      }
      return true;
   }

   // This boolean is an explicit call-site assertion, NOT authentication.
   // Production wiring must expose this only through a trusted owner-only UI.
   bool Rearm(const bool trusted_owner_confirmed,string &reason)
   {
      reason="";
      if(!m_initialized || !m_locked)
      { reason="Overall-loss lock is not active or guard is uninitialized"; return false; }
      if(!trusted_owner_confirmed)
      { reason="Trusted owner confirmation is required"; return false; }
      if(!VerifyAccount(reason)) return false;
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      double minimum_equity=m_original_deposit*(1.0-m_loss_limit_percent/100.0);
      if(!MathIsValidNumber(equity) || equity<=minimum_equity)
      { reason="Equity must recover above the 50% loss boundary before manual reactivation"; return false; }
      m_locked=false;
      if(!Persist())
      {
         m_locked=true;
         reason="Reactivation persistence failed; overall-loss lock remains active";
         return false;
      }
      reason="Overall-loss lock manually rearmed; immutable original-deposit baseline retained";
      return true;
   }

   bool IsLocked(void) const { return (!m_initialized || m_locked); }
   bool IsInitialized(void) const { return m_initialized; }
   double OriginalDeposit(void) const { return m_original_deposit; }
   double LossLimitPercent(void) const { return m_loss_limit_percent; }
};

#endif
