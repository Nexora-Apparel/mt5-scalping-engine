#define VELTRIX_RISK_TEST
#include "../Include/Veltrix/OverallAccountLossGuard.mqh"

#define VX_OVERALL_RESULT "veltrix_overall_loss_guard_runtime_test.result"

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

void WriteResult(const string value)
{
   int handle=FileOpen(VX_OVERALL_RESULT,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE) { Print("OVERALL LOSS TEST FAIL | result file unavailable"); return; }
   FileWriteString(handle,value);
   FileFlush(handle);
   FileClose(handle);
}

void Fail(const string message)
{
   Print("OVERALL LOSS TEST FAIL | ",message);
   WriteResult("FAIL | "+message);
}

bool ExpectInitFailure(const long login,const string server,const double baseline,
                       const bool verified,const string expected,string &reason)
{
   CVxOverallAccountLossGuard guard;
   string actual="";
   if(guard.Init(login,server,baseline,verified,actual))
   { reason="guard unexpectedly initialized"; return false; }
   if(StringFind(actual,expected)<0)
   { reason="unexpected fail-closed reason: "+actual; return false; }
   reason="";
   return true;
}

void OnStart()
{
   long login=910000000+(long)(GetTickCount64()%800000000);
   string server="VELTRIX_OVERALL_GUARD_RUNTIME_TEST";
   string suffix=StringFormat("%I64d_%I64u",login,TestHash64(server));
   string baseline_key="VX_ORIGDEP_"+suffix;
   string lock_key="VX_OVERALL_LOCK_"+suffix;
   string checksum_key="VX_OVERALL_SUM_"+suffix;
   string audit_file="VELTRIX_OVERALL_AUDIT_"+suffix+".csv";
   string reason="";

   GlobalVariableDel(baseline_key);
   GlobalVariableDel(lock_key);
   GlobalVariableDel(checksum_key);
   FileDelete(audit_file,FILE_COMMON);

   if(!ExpectInitFailure(login,server,10000.0,false,
                         "independently owner-verified original deposit",reason))
   { Fail("unverified baseline rejection | "+reason); return; }

   CVxOverallAccountLossGuard guard;
   if(!guard.Init(login,server,10000.0,true,reason))
   { Fail("initial verified baseline | "+reason); return; }
   if(guard.IsLocked() || MathAbs(guard.OriginalDeposit()-10000.0)>0.001)
   { Fail("initial state or original-deposit value incorrect"); return; }

   if(guard.EvaluateEquitySnapshotForTest(5001.0,reason)==false || guard.IsLocked())
   { Fail("equity above 50% threshold was incorrectly locked | "+reason); return; }

   if(guard.EvaluateEquitySnapshotForTest(5000.0,reason) || !guard.IsLocked())
   { Fail("exact 50% threshold did not latch lock | "+reason); return; }
   if(!GlobalVariableCheck(lock_key) || GlobalVariableGet(lock_key)!=1.0)
   { Fail("overall-loss lock was not durably persisted"); return; }

   CVxOverallAccountLossGuard restarted;
   if(!restarted.Init(login,server,10000.0,true,reason) || !restarted.IsLocked())
   { Fail("lock did not survive object/terminal restart replay | "+reason); return; }

   if(ExpectInitFailure(login,server,10001.0,true,
                        "conflicts with the immutable stored baseline",reason)==false)
   { Fail("changed original-deposit baseline was accepted | "+reason); return; }

   if(restarted.RearmEquitySnapshotForTest("TEST_OWNER","Recovered above threshold after review",
                                           "VELTRIX OWNER CONFIRM REACTIVATION",5000.0,reason) ||
      !restarted.IsLocked())
   { Fail("rearm at or below threshold was accepted"); return; }

   if(restarted.RearmEquitySnapshotForTest("","Recovered above threshold after review",
                                           "VELTRIX OWNER CONFIRM REACTIVATION",6000.0,reason) ||
      !restarted.IsLocked())
   { Fail("reactivation without an operator identity was accepted"); return; }

   if(restarted.RearmEquitySnapshotForTest("TEST_OWNER","Reviewed account and confirmed manual restart",
                                           "wrong phrase",6000.0,reason) ||
      !restarted.IsLocked())
   { Fail("reactivation without the exact owner confirmation phrase was accepted"); return; }

   if(!restarted.RearmEquitySnapshotForTest("TEST_OWNER","Reviewed account and confirmed manual restart",
                                            "VELTRIX OWNER CONFIRM REACTIVATION",6000.0,reason) ||
      restarted.IsLocked())
   { Fail("manual rearm above threshold failed | "+reason); return; }
   if(MathAbs(GlobalVariableGet(baseline_key)-10000.0)>0.001)
   { Fail("manual rearm changed immutable original-deposit baseline"); return; }

   CVxOverallAccountLossGuard after_rearm;
   if(!after_rearm.Init(login,server,10000.0,true,reason) || after_rearm.IsLocked())
   { Fail("manual rearm audit did not survive restart | "+reason); return; }
   if(!FileIsExist(audit_file,FILE_COMMON))
   { Fail("owner reactivation audit journal was not created"); return; }

   if(after_rearm.EvaluateEquitySnapshotForTest(4999.0,reason) ||
      !after_rearm.IsLocked())
   { Fail("second threshold breach did not relatch after rearm"); return; }

   double saved_checksum=GlobalVariableGet(checksum_key);
   GlobalVariableSet(checksum_key,saved_checksum+1.0);
   if(!ExpectInitFailure(login,server,10000.0,true,
                         "checksum mismatch",reason))
   { Fail("checksum corruption was not rejected | "+reason); return; }
   GlobalVariableSet(checksum_key,saved_checksum);

   int audit_handle=FileOpen(audit_file,FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(audit_handle==INVALID_HANDLE)
   { Fail("could not open audit file for tamper test"); return; }
   FileSeek(audit_handle,0,SEEK_END);
   FileWriteString(audit_handle,"BROKEN_AUDIT_RECORD");
   FileFlush(audit_handle);
   FileClose(audit_handle);
   if(!ExpectInitFailure(login,server,10000.0,true,
                         "audit journal",reason))
   { Fail("audit-chain corruption was not rejected | "+reason); return; }

   GlobalVariableDel(lock_key);
   if(!ExpectInitFailure(login,server,10000.0,true,
                         "persistent state is partial",reason))
   { Fail("partial persistent state was not rejected | "+reason); return; }

   GlobalVariableDel(baseline_key);
   GlobalVariableDel(lock_key);
   GlobalVariableDel(checksum_key);
   FileDelete(audit_file,FILE_COMMON);

   Print("OVERALL LOSS GUARD RUNTIME TEST PASS | verified_baseline=true threshold_latch=true persistent_lock=true immutable_baseline=true audited_owner_rearm=true invalid_owner_confirmation_rejected=true rearm_threshold=true restart_replay=true checksum_tamper_rejected=true partial_state_rejected=true");
   WriteResult("PASS | verified original deposit, 50% threshold lock, persistent restart replay, immutable baseline, audited owner reactivation, invalid owner confirmation rejection, checksum tamper rejection, partial-state rejection");
}
