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
   string m_audit_filename;
   long m_audit_sequence;
   string m_audit_previous_hash;
   bool m_audit_locked;
   bool m_audit_pending;

   string AuditPayload(const long sequence,const string event_type,
                       const string operator_id,const string detail,
                       const long timestamp_msc,const double equity,
                       const double baseline,const string previous_hash) const
   {
      return StringFormat("%I64d|%s|%s|%s|%I64d|%.17g|%.17g|%s",
                          sequence,event_type,operator_id,detail,
                          timestamp_msc,equity,baseline,previous_hash);
   }

   bool SafeAuditText(const string value,const int minimum_length,const int maximum_length) const
   {
      int length=StringLen(value);
      if(length<minimum_length || length>maximum_length) return false;
      if(StringFind(value,";")>=0 || StringFind(value,"|")>=0 ||
         StringFind(value,"\n")>=0 || StringFind(value,"\r")>=0)
         return false;
      return true;
   }

   bool InitializeAudit(const bool new_account_state,string &reason)
   {
      reason="";
      m_audit_filename="VELTRIX_OVERALL_AUDIT_"+AccountSuffix(m_expected_login,m_expected_server)+".csv";
      if(StringLen(m_audit_filename)>63)
      { reason="Overall-loss audit filename exceeds terminal limits"; return false; }
      bool exists=FileIsExist(m_audit_filename,FILE_COMMON);
      if(!exists && !new_account_state)
      { reason="Overall-loss audit history is missing for an existing account state; refusing reactivation"; return false; }
      if(!exists)
      {
         int create=FileOpen(m_audit_filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
         if(create==INVALID_HANDLE)
         { reason="Could not create account-scoped overall-loss audit journal"; return false; }
         FileFlush(create);
         FileClose(create);
      }
      int handle=FileOpen(m_audit_filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
      if(handle==INVALID_HANDLE)
      { reason="Could not open overall-loss audit journal"; return false; }
      m_audit_sequence=0;
      m_audit_previous_hash="0";
      m_audit_locked=false;
      m_audit_pending=false;
      FileSeek(handle,0,SEEK_SET);
      while(!FileIsEnding(handle))
      {
         double seq_number=FileReadNumber(handle);
         if(FileIsEnding(handle) && seq_number==0.0) break;
         string event_type=FileReadString(handle);
         string operator_id=FileReadString(handle);
         string detail=FileReadString(handle);
         double timestamp_number=FileReadNumber(handle);
         double equity=FileReadNumber(handle);
         double baseline=FileReadNumber(handle);
         string previous_hash=FileReadString(handle);
         string checksum=FileReadString(handle);
         if(!MathIsValidNumber(seq_number) || !MathIsValidNumber(timestamp_number) ||
            !MathIsValidNumber(equity) || !MathIsValidNumber(baseline) ||
            seq_number!=(double)(m_audit_sequence+1) || timestamp_number<=0.0 ||
            operator_id=="" || detail=="" || previous_hash!=m_audit_previous_hash ||
            (event_type!="LOCK" && event_type!="REARM_INTENT" &&
             event_type!="REARM_COMMIT" && event_type!="REARM_ABORT"))
         {
            FileClose(handle);
            reason="Overall-loss audit journal contains a malformed or out-of-sequence record";
            return false;
         }
         string payload=AuditPayload((long)seq_number,event_type,operator_id,detail,
                                      (long)timestamp_number,equity,baseline,previous_hash);
         string expected=StringFormat("%I64u",Hash64(payload));
         if(checksum!=expected || MathAbs(baseline-m_original_deposit)>
            MathMax(0.01,m_original_deposit*1e-8))
         {
            FileClose(handle);
            reason="Overall-loss audit checksum or immutable baseline validation failed";
            return false;
         }
         if(event_type=="LOCK")
         { m_audit_locked=true; m_audit_pending=false; }
         else if(event_type=="REARM_INTENT")
         { m_audit_locked=true; m_audit_pending=true; }
         else if(event_type=="REARM_COMMIT")
         {
            if(!m_audit_pending)
            { FileClose(handle); reason="Overall-loss audit has a reactivation commit without an intent"; return false; }
            m_audit_locked=false; m_audit_pending=false;
         }
         else if(event_type=="REARM_ABORT")
         { m_audit_locked=true; m_audit_pending=false; }
         m_audit_sequence=(long)seq_number;
         m_audit_previous_hash=checksum;
      }
      FileSeek(handle,0,SEEK_END);
      FileClose(handle);
      return true;
   }

   bool AppendAudit(const string event_type,const string operator_id,
                    const string detail,const double equity,
                    const long timestamp_msc,string &reason)
   {
      reason="";
      if(!SafeAuditText(operator_id,1,64) || !SafeAuditText(detail,1,240) ||
         !MathIsValidNumber(equity) || equity<=0.0 || timestamp_msc<=0)
      { reason="Overall-loss audit event fields are invalid"; return false; }
      int handle=FileOpen(m_audit_filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
      if(handle==INVALID_HANDLE)
      { reason="Could not append overall-loss audit event"; return false; }
      long sequence=m_audit_sequence+1;
      string payload=AuditPayload(sequence,event_type,operator_id,detail,
                                  timestamp_msc,equity,m_original_deposit,
                                  m_audit_previous_hash);
      string checksum=StringFormat("%I64u",Hash64(payload));
      FileSeek(handle,0,SEEK_END);
      ResetLastError();
      uint written=FileWrite(handle,(double)sequence,event_type,operator_id,detail,
                             (double)timestamp_msc,equity,m_original_deposit,
                             m_audit_previous_hash,checksum);
      if(written==0)
      { FileClose(handle); reason="Overall-loss audit append failed"; return false; }
      ResetLastError();
      FileFlush(handle);
      int error=GetLastError();
      FileClose(handle);
      if(error!=0)
      { reason="Overall-loss audit flush failed"; return false; }
      m_audit_sequence=sequence;
      m_audit_previous_hash=checksum;
      if(event_type=="LOCK") { m_audit_locked=true; m_audit_pending=false; }
      else if(event_type=="REARM_INTENT") { m_audit_locked=true; m_audit_pending=true; }
      else if(event_type=="REARM_COMMIT") { m_audit_locked=false; m_audit_pending=false; }
      else if(event_type=="REARM_ABORT") { m_audit_locked=true; m_audit_pending=false; }
      return true;
   }

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
      if(AccountInfoString(ACCOUNT_CURRENCY)!="USD")
      { reason="Overall-loss guard requires a USD-denominated DEMO account"; return false; }
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
      m_audit_filename="";
      m_audit_sequence=0;
      m_audit_previous_hash="0";
      m_audit_locked=false;
      m_audit_pending=false;
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
      bool new_account_state=(!has_baseline && !has_lock && !has_checksum);
      if(!InitializeAudit(new_account_state,reason))
      { m_initialized=false; return false; }
      // An unfinished reactivation intent is never treated as approval after a crash.
      if(m_audit_locked || m_audit_pending)
      {
         m_locked=true;
         if(!Persist())
         { m_initialized=false; reason="Audit replay requires the overall-loss lock, but lock reconciliation failed"; return false; }
      }
      // Broker identity and live equity are checked on every live evaluation.
      m_initialized=true;
      return true;
   }

   bool EvaluateEquityValue(const double equity,string &reason)
   {
      reason="";
      if(!m_initialized)
      { reason="Overall-loss guard is not initialized"; return false; }
      if(m_locked)
      { reason="50% original-deposit loss ceiling is latched pending owner reactivation"; return false; }
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
         string audit_reason="";
         if(!AppendAudit("LOCK","SYSTEM","50_PERCENT_ORIGINAL_DEPOSIT_THRESHOLD",
                         equity,(long)TimeLocal()*1000,audit_reason))
         { reason="Overall-loss lock persisted, but audit append failed: "+audit_reason; return false; }
         reason="50% original-deposit account-loss ceiling reached; only the manual owner reactivation script can request reactivation";
         return false;
      }
      return true;
   }

   bool RearmEquityValue(const string operator_id,const string owner_reason,
                          const string confirmation_phrase,const double equity,
                          string &reason)
   {
      reason="";
      if(!m_initialized || !m_locked)
      { reason="Overall-loss lock is not active or guard is uninitialized"; return false; }
      if(!SafeAuditText(operator_id,3,64) || !SafeAuditText(owner_reason,10,240))
      { reason="A valid operator ID and a specific reactivation reason are required"; return false; }
      if(confirmation_phrase!="VELTRIX OWNER CONFIRM REACTIVATION")
      { reason="Exact manual owner confirmation phrase is required"; return false; }
      double minimum_equity=m_original_deposit*(1.0-m_loss_limit_percent/100.0);
      if(!MathIsValidNumber(equity) || equity<=minimum_equity)
      { reason="Equity must recover above the 50% loss boundary before manual reactivation"; return false; }
      long now_msc=(long)TimeLocal()*1000;
      if(!AppendAudit("REARM_INTENT",operator_id,owner_reason,equity,now_msc,reason))
         return false;
      m_locked=false;
      if(!Persist())
      {
         m_locked=true;
         Persist();
         string audit_reason="";
         AppendAudit("REARM_ABORT",operator_id,"PERSISTENCE_FAILURE",equity,
                     (long)TimeLocal()*1000,audit_reason);
         reason="Reactivation persistence failed; overall-loss lock remains active";
         return false;
      }
      string commit_reason="";
      if(!AppendAudit("REARM_COMMIT",operator_id,owner_reason,equity,
                      (long)TimeLocal()*1000,commit_reason))
      {
         m_locked=true;
         Persist();
         reason="Reactivation audit commit failed; overall-loss lock was restored: "+commit_reason;
         return false;
      }
      reason="Owner-requested reactivation audited; immutable original-deposit baseline retained";
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
      return EvaluateEquityValue(AccountInfoDouble(ACCOUNT_EQUITY),reason);
   }

   // This boolean is an explicit call-site assertion, NOT authentication.
   // Production wiring must expose this only through a trusted owner-only UI.
   // Called only by the manually launched owner-rearm script. Operator ID and
   // reason are audit attribution supplied by the operator, not cryptographic identity.
   bool Rearm(const string operator_id,const string owner_reason,
              const string confirmation_phrase,string &reason)
   {
      reason="";
      if(!m_initialized || !m_locked)
      { reason="Overall-loss lock is not active or guard is uninitialized"; return false; }
      if(!VerifyAccount(reason)) return false;
      return RearmEquityValue(operator_id,owner_reason,confirmation_phrase,
                              AccountInfoDouble(ACCOUNT_EQUITY),reason);
   }

#ifdef VELTRIX_RISK_TEST
   // Synthetic equity injection exists only in dedicated runtime-test builds.
   bool EvaluateEquitySnapshotForTest(const double equity,string &reason)
   {
      return EvaluateEquityValue(equity,reason);
   }

   bool RearmEquitySnapshotForTest(const string operator_id,const string owner_reason,
                                   const string confirmation_phrase,const double equity,
                                   string &reason)
   {
      return RearmEquityValue(operator_id,owner_reason,confirmation_phrase,equity,reason);
   }
#endif

   bool IsLocked(void) const { return (!m_initialized || m_locked); }
   bool IsInitialized(void) const { return m_initialized; }
   double OriginalDeposit(void) const { return m_original_deposit; }
   double LossLimitPercent(void) const { return m_loss_limit_percent; }
};

#endif
