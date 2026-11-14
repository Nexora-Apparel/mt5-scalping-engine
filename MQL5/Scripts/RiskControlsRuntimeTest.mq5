#define VELTRIX_RISK_TEST
#include "../Include/Veltrix/RiskControls.mqh"
#include "../Include/Veltrix/PortfolioExposureLedger.mqh"

#define VX_CONTROLS_RESULT "veltrix_risk_controls_runtime_test.result"

ulong TestHash64(const string value)
{
   ulong hash=14695981039346656037;
   for(int i=0;i<StringLen(value);i++)
   {
      hash^=(ulong)StringGetCharacter(value,i);
      hash*=1099511628211;
   }
   return hash;
}

string TestSuffix(const long login,const string server)
{
   return StringFormat("%I64d_%I64u",login,TestHash64(server));
}

void WriteControlsResult(const string value)
{
   int handle=FileOpen(VX_CONTROLS_RESULT,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE)
   {
      Print("RISK CONTROLS RUNTIME TEST FAIL | could not write result sentinel");
      return;
   }
   FileWriteString(handle,value);
   FileFlush(handle);
   FileClose(handle);
}

void FailControlsTest(const string message)
{
   Print("RISK CONTROLS RUNTIME TEST FAIL | ",message);
   WriteControlsResult("FAIL | "+message);
}

bool BuildConfig(const long login,const string server,VxRiskControlConfig &config)
{
   config.expected_demo_login=login;
   config.expected_demo_server=server;
   config.risk_per_trade_percent=0.10;
   config.max_portfolio_risk_percent=0.25;
   config.max_daily_loss_percent=15.00;
   config.verified_original_deposit=10000.0;
   config.original_deposit_verified=true;
   config.cooldown_seconds=0; // No trade-frequency pause in the multi-position policy.
   config.max_consecutive_losses=0; // No consecutive-loss daily lock.
   return true;
}

bool SeedEmergencyStop(const long login,const string server,
                       const VxRiskControlConfig &config,string &reason)
{
   CVxRiskControls controls;
   if(!controls.Init(config,reason))
      return false;
   if(!controls.LatchEmergencyStop(reason))
      return false;
   return controls.IsEmergencyStopped();
}

bool AppendSyntheticDailyLock(const long login,const string server,
                              const long day_key,const long timestamp_msc,
                              string &reason)
{
   CVxRiskJournal journal;
   if(!journal.Init(login,server,reason))
      return false;
   bool ok=journal.AppendDailyLock(day_key,timestamp_msc,1.0,reason);
   journal.Close();
   return ok;
}

bool VerifyRestoredLocks(const long login,const string server,
                         const VxRiskControlConfig &config,string &reason)
{
   CVxRiskControls controls;
   if(!controls.Init(config,reason))
      return false;
   if(!controls.IsEmergencyStopped())
   { reason="Permanent emergency-stop event was not restored"; return false; }
   if(!controls.IsDailyLossLocked())
   { reason="Server-day loss-lock event was not restored"; return false; }
   return true;
}

bool ExpectInitFailure(const long login,const string server,
                       const VxRiskControlConfig &config,
                       const string expected_fragment,string &reason)
{
   CVxRiskControls controls;
   string actual_reason="";
   bool initialized=controls.Init(config,actual_reason);
   if(initialized)
   { reason="Risk controls unexpectedly initialized despite injected failure"; return false; }
   if(StringFind(actual_reason,expected_fragment)<0)
   { reason="Unexpected fail-closed reason: "+actual_reason; return false; }
   reason="";
   return true;
}


bool RunDailyRearmControlTests(string &reason)
{
   long login=900000000+(long)(GetTickCount64()%900000000);
   string server="VELTRIX_DAILY_REARM_RUNTIME_TEST";
   string suffix=TestSuffix(login,server);
   string emergency_key="VX_ESTOP_"+suffix;
   string day_key_name="VX_DAY_"+suffix;
   string equity_key="VX_EQ_"+suffix;
   string daily_lock_key="VX_LOCK_"+suffix;
   string loss_key="VX_LS_"+suffix;
   string cooldown_key="VX_CD_"+suffix;
   string checksum_key="VX_CSUM_"+suffix;
   string transaction_lock_key="VX_LOCKTX_"+suffix;
   string original_deposit_key="VX_ORIGDEP_"+suffix;
   string overall_lock_key="VX_OVERALL_LOCK_"+suffix;
   string overall_checksum_key="VX_OVERALL_SUM_"+suffix;
   string journal_file=StringFormat("VELTRIX_XAUUSD_RISK_%I64d_%I64u.csv",
                                    login,TestHash64(server));
   string overall_audit_file="VELTRIX_OVERALL_AUDIT_"+suffix+".csv";
   long now_msc=(long)TimeLocal()*1000;
   long day_key=20261114;
   double initial_equity=10000.0;
   double rearmed_equity=9875.50;
   VxRiskControlConfig config;
   BuildConfig(login,server,config);
   bool ok=true;
   string local_reason="";

   CVxRiskJournal seed;
   if(!seed.Init(login,server,local_reason) ||
      !seed.AppendDailyLock(day_key,now_msc+1,15.0,local_reason))
   {
      reason="could not seed audited daily lock: "+local_reason;
      ok=false;
   }
   seed.Close();

   string serialized=StringFormat("0|%I64d|%.17g|1|0|0",day_key,initial_equity);
   double checksum=(double)(TestHash64(serialized)%9007199254740991);
   if(ok &&
      (GlobalVariableSet(day_key_name,(double)day_key)==0 ||
       GlobalVariableSet(equity_key,initial_equity)==0 ||
       GlobalVariableSet(daily_lock_key,1.0)==0 ||
       GlobalVariableSet(loss_key,0.0)==0 ||
       GlobalVariableSet(cooldown_key,0.0)==0 ||
       GlobalVariableSet(emergency_key,0.0)==0 ||
       GlobalVariableSet(checksum_key,checksum)==0 ||
       GlobalVariableSet(transaction_lock_key,0.0)==0))
   {
      reason="could not seed checksum-valid daily-lock state";
      ok=false;
   }

   if(ok)
   {
      CVxRiskControls controls;
      if(!controls.Init(config,local_reason) || !controls.IsDailyLossLocked() ||
         controls.IsEmergencyStopped())
      {
         reason="daily-lock control initialization failed: "+local_reason;
         ok=false;
      }
      else
      {
         if(controls.RearmDailyLossLockForTest(
               rearmed_equity,now_msc+10,"owner-01",
               "Manual recovery after equity and statement review",
               "statement-2026-11-14","INVALID CONFIRMATION",local_reason))
         {
            reason="daily reactivation accepted an invalid owner confirmation";
            ok=false;
         }
         if(ok && controls.RearmDailyLossLockForTest(
               rearmed_equity,now_msc+11,"","Manual recovery after equity and statement review",
               "statement-2026-11-14","VELTRIX OWNER CONFIRM DAILY REACTIVATION",local_reason))
         {
            reason="daily reactivation accepted missing operator attribution";
            ok=false;
         }
         if(ok && !controls.RearmDailyLossLockForTest(
               rearmed_equity,now_msc+12,"owner-01",
               "Manual recovery after equity and statement review",
               "statement-2026-11-14","VELTRIX OWNER CONFIRM DAILY REACTIVATION",local_reason))
         {
            reason="audited daily reactivation core failed: "+local_reason;
            ok=false;
         }
         if(ok && (controls.IsDailyLossLocked() || controls.IsEmergencyStopped() ||
                   MathAbs(GlobalVariableGet(equity_key)-rearmed_equity)>1e-8 ||
                   GlobalVariableGet(daily_lock_key)!=0.0))
         {
            reason="daily reactivation did not persist unlocked state and replacement equity baseline";
            ok=false;
         }
      }
   }

   if(ok)
   {
      CVxRiskJournal verify;
      if(!verify.Init(login,server,local_reason) ||
         verify.HasDailyLock(day_key) || !verify.HasDailyRearm(day_key) ||
         verify.DailyRearmOperatorId(day_key)!="owner-01" ||
         verify.DailyRearmReason(day_key)!="Manual recovery after equity and statement review" ||
         verify.DailyRearmEvidenceReference(day_key)!="statement-2026-11-14")
      {
         reason="daily rearm audit metadata/replay verification failed: "+local_reason;
         ok=false;
      }
      verify.Close();
   }

   if(ok)
   {
      CVxRiskControls restored;
      if(!restored.Init(config,local_reason) || restored.IsDailyLossLocked() ||
         restored.IsEmergencyStopped() ||
         MathAbs(GlobalVariableGet(equity_key)-rearmed_equity)>1e-8)
      {
         reason="daily rearm state did not survive risk-control restart: "+local_reason;
         ok=false;
      }
   }

   FileDelete(journal_file,FILE_COMMON);
   FileDelete(overall_audit_file,FILE_COMMON);
   string keys[8];
   keys[0]=emergency_key; keys[1]=day_key_name;
   keys[2]=equity_key; keys[3]=daily_lock_key;
   keys[4]=loss_key; keys[5]=cooldown_key;
   keys[6]=checksum_key; keys[7]=transaction_lock_key;
   for(int i=0;i<8;i++) GlobalVariableDel(keys[i]);
   GlobalVariableDel(original_deposit_key);
   GlobalVariableDel(overall_lock_key);
   GlobalVariableDel(overall_checksum_key);
   if(!ok) return false;
   reason="";
   return true;
}

bool RunPortfolioLedgerTests(string &reason)
{
   CVxPortfolioExposureLedger ledger;
   for(int i=1;i<=12;i++)
   {
      string local_reason="";
      if(!ledger.Register(i,(ulong)(1000+i),2.5,4.0,local_reason))
      { reason="register multi-position exposure "+IntegerToString(i)+": "+local_reason; return false; }
   }
   if(ledger.Count()!=12 || ledger.ActiveCount()!=12 ||
      MathAbs(ledger.AggregateOpenRiskMoney()-30.0)>1e-8 ||
      MathAbs(ledger.AggregateMarginMoney()-48.0)>1e-8)
   { reason="uncapped portfolio aggregation mismatch"; return false; }

   if(!ledger.MarkUnknown(1) || !ledger.MarkProtectionFailure(2) ||
      !ledger.MarkClosePending(3))
   { reason="could not mark unresolved exposure states"; return false; }
   if(MathAbs(ledger.AggregateOpenRiskMoney()-30.0)>1e-8 ||
      MathAbs(ledger.AggregateMarginMoney()-48.0)>1e-8)
   { reason="unresolved positions were incorrectly removed from exposure"; return false; }

   if(!ledger.UpdateStopRisk(4,1.0) || ledger.UpdateStopRisk(4,3.0))
   { reason="stop-risk reduction/widening policy failed"; return false; }
   if(MathAbs(ledger.AggregateOpenRiskMoney()-28.5)>1e-8)
   { reason="reduced stop risk did not update aggregate exposure"; return false; }

   if(ledger.ConfirmClosed(1,false) ||
      MathAbs(ledger.AggregateOpenRiskMoney()-28.5)>1e-8)
   { reason="unconfirmed broker close released risk"; return false; }
   if(!ledger.ConfirmClosed(1,true) ||
      MathAbs(ledger.AggregateOpenRiskMoney()-26.0)>1e-8 ||
      ledger.Count()!=11 || ledger.ActiveCount()!=11)
   { reason="confirmed broker close did not release exposure"; return false; }

   VxRiskRequest request;
   request.equity=10000.0;
   request.risk_percent=0.10;
   request.stop_distance_price=0.10;
   request.tick_size=0.01;
   request.tick_value_loss=1.0;
   request.volume_min=0.01;
   request.volume_max=100.0;
   request.volume_step=0.01;
   request.current_open_risk_money=0.0; // Must be overwritten from the ledger.
   request.max_portfolio_risk_percent=0.50;
   request.open_positions=0;
   VxRiskDecision sizing;
   if(!VxCalculateRiskVolume(request,sizing))
   { reason="baseline risk sizing unexpectedly failed"; return false; }
   request.current_open_risk_money=ledger.AggregateOpenRiskMoney();
   request.open_positions=ledger.ActiveCount();
   if(!VxCalculateRiskVolume(request,sizing) || sizing.volume<=0.0 ||
      MathAbs(sizing.portfolio_capacity_money-24.0)>1e-8)
   { reason="aggregate ledger capacity was not applied to dynamic lot sizing"; return false; }

   string duplicate_reason="";
   if(ledger.Register(2,9999,1.0,1.0,duplicate_reason))
   { reason="duplicate position identifier was accepted"; return false; }
   if(ledger.Register(99,1002,1.0,1.0,duplicate_reason))
   { reason="duplicate broker ticket was accepted"; return false; }
   if(!ledger.UpdateMargin(5,6.0) ||
      MathAbs(ledger.AggregateMarginMoney()-46.0)>1e-8)
   { reason="fresh margin estimate did not update aggregate margin"; return false; }
   reason="";
   return true;
}

void OnStart()
{
   string daily_rearm_reason="";
   if(!RunDailyRearmControlTests(daily_rearm_reason))
   {
      FailControlsTest("audited daily reactivation control path | "+daily_rearm_reason);
      return;
   }

   string portfolio_reason="";
   if(!RunPortfolioLedgerTests(portfolio_reason))
   {
      FailControlsTest("portfolio exposure ledger | "+portfolio_reason);
      return;
   }

   // Synthetic identity only. No broker account or credential is read.
   long test_login=900000000+(long)(GetTickCount64()%900000000);
   string test_server="VELTRIX_RISK_CONTROLS_RUNTIME_TEST";
   string suffix=TestSuffix(test_login,test_server);
   string emergency_key="VX_ESTOP_"+suffix;
   string day_key_name="VX_DAY_"+suffix;
   string equity_key="VX_EQ_"+suffix;
   string daily_lock_key="VX_LOCK_"+suffix;
   string loss_key="VX_LS_"+suffix;
   string cooldown_key="VX_CD_"+suffix;
   string checksum_key="VX_CSUM_"+suffix;
   string transaction_lock_key="VX_LOCKTX_"+suffix;
   string original_deposit_key="VX_ORIGDEP_"+suffix;
   string overall_lock_key="VX_OVERALL_LOCK_"+suffix;
   string overall_checksum_key="VX_OVERALL_SUM_"+suffix;
   string journal_file=StringFormat("VELTRIX_XAUUSD_RISK_%I64d_%I64u.csv",
                                    test_login,TestHash64(test_server));
   long now_msc=(long)TimeLocal()*1000;
   long day_key=20261113;
   VxRiskControlConfig config;
   BuildConfig(test_login,test_server,config);
   string reason="";

   if(!SeedEmergencyStop(test_login,test_server,config,reason))
   {
      FailControlsTest("seed emergency stop | "+reason);
      return;
   }

   if(!AppendSyntheticDailyLock(test_login,test_server,day_key,now_msc+1,reason))
   {
      FailControlsTest("append synthetic daily lock | "+reason);
      return;
   }

   // Populate a verified-looking baseline and matching checksum for the
   // synthetic identity. This test does not call broker-sensitive methods.
   double equity=10000.0;
   string serialized=StringFormat("1|%I64d|%.17g|0|0|0",
                                  day_key,equity);
   double checksum=(double)(TestHash64(serialized)%9007199254740991);
   if(GlobalVariableSet(day_key_name,(double)day_key)==0 ||
      GlobalVariableSet(equity_key,equity)==0 ||
      GlobalVariableSet(daily_lock_key,0.0)==0 ||
      GlobalVariableSet(loss_key,0.0)==0 ||
      GlobalVariableSet(cooldown_key,0.0)==0 ||
      GlobalVariableSet(emergency_key,1.0)==0 ||
      GlobalVariableSet(checksum_key,checksum)==0 ||
      GlobalVariableSet(transaction_lock_key,0.0)==0)
   {
      FailControlsTest("could not prepare synthetic terminal-global risk state");
      return;
   }

   if(!VerifyRestoredLocks(test_login,test_server,config,reason))
   {
      FailControlsTest("journal lock restoration | "+reason);
      return;
   }

   // An abandoned transaction lock must block startup.
   if(GlobalVariableSet(transaction_lock_key,(double)(now_msc+2))==0 ||
      !ExpectInitFailure(test_login,test_server,config,
                         "prior risk-state transaction did not finish",reason))
   {
      FailControlsTest("abandoned transaction-lock fail-closed test | "+reason);
      return;
   }
   GlobalVariableSet(transaction_lock_key,0.0);

   // Alter one state value without updating the commit checksum. Startup
   // must reject the inconsistent snapshot; restore it before cleanup.
   if(GlobalVariableSet(equity_key,equity+1.0)==0 ||
      !ExpectInitFailure(test_login,test_server,config,
                         "checksum mismatch",reason))
   {
      FailControlsTest("risk-state checksum fail-closed test | "+reason);
      return;
   }
   GlobalVariableSet(equity_key,equity);

   if(!FileDelete(journal_file,FILE_COMMON))
   {
      FailControlsTest("synthetic journal cleanup failed");
      return;
   }
   string keys[8];
   keys[0]=emergency_key; keys[1]=day_key_name;
   keys[2]=equity_key; keys[3]=daily_lock_key;
   keys[4]=loss_key; keys[5]=cooldown_key;
   keys[6]=checksum_key; keys[7]=transaction_lock_key;
   for(int i=0;i<8;i++)
      GlobalVariableDel(keys[i]);
   GlobalVariableDel(original_deposit_key);
   GlobalVariableDel(overall_lock_key);
   GlobalVariableDel(overall_checksum_key);

   PrintFormat("RISK CONTROLS RUNTIME TEST PASS | synthetic_identity=true emergency_stop_restore=true daily_lock_restore=true audited_daily_rearm=true daily_rearm_restart=true abandoned_lock_blocked=true checksum_mismatch_blocked=true cleanup=true portfolio_exposure_ledger=true uncapped_positions=true unresolved_risk_retained=true");
   WriteControlsResult("PASS | emergency-stop/daily-lock restore, audited daily rearm core, owner metadata replay, rearm restart recovery, abandoned transaction-lock rejection, checksum mismatch rejection, multi-position exposure ledger");
}
