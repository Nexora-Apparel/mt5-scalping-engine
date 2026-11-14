#include "../Include/Veltrix/RiskJournal.mqh"

#define VX_RISK_JOURNAL_TEST_RESULT "veltrix_risk_journal_runtime_test.result"

void WriteRiskJournalResult(const string value)
{
   int handle=FileOpen(VX_RISK_JOURNAL_TEST_RESULT,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE)
   {
      Print("RISK JOURNAL RUNTIME TEST FAIL | could not write result sentinel");
      return;
   }
   FileWriteString(handle,value);
   FileFlush(handle);
   FileClose(handle);
}

void FailRiskJournalTest(const string message)
{
   Print("RISK JOURNAL RUNTIME TEST FAIL | ",message);
   WriteRiskJournalResult("FAIL | "+message);
}

void OnStart()
{
   // Synthetic identity only: this test never connects to a broker or account.
   long test_login=900000000+(long)(GetTickCount64()%900000000);
   string test_server="VELTRIX_RISK_JOURNAL_RUNTIME_TEST";
   string request_key=StringFormat("REQ_%I64u",GetTickCount64());
   string close_key=StringFormat("CLOSE_%I64u",GetTickCount64()+1);
   long now_msc=(long)TimeLocal()*1000;

   CVxRiskJournal journal;
   string reason;
   if(!journal.Init(test_login,test_server,reason))
   {
      FailRiskJournalTest("initialization | "+reason);
      return;
   }
   if(journal.Count()!=0)
   {
      FailRiskJournalTest("new synthetic journal unexpectedly contained records");
      return;
   }
   if(!journal.AppendRequest(request_key,now_msc,reason) ||
      !journal.HasRequest(request_key))
   {
      FailRiskJournalTest("request append/read | "+reason);
      return;
   }
   if(journal.AppendRequest(request_key,now_msc+1,reason))
   {
      FailRiskJournalTest("duplicate request identifier was accepted");
      return;
   }
   if(!journal.AppendClose(close_key,now_msc+2,-1.25,reason) ||
      !journal.HasClose(close_key))
   {
      FailRiskJournalTest("closing-deal append/read | "+reason);
      return;
   }
   if(journal.AppendClose(close_key,now_msc+3,-1.25,reason))
   {
      FailRiskJournalTest("duplicate closing-deal identifier was accepted");
      return;
   }
   if(!journal.AppendDailyLock(20261113,now_msc+4,1.0,reason) ||
      !journal.HasDailyLock(20261113) || journal.ActiveDailyLockDay()!=20261113)
   {
      FailRiskJournalTest("daily-lock event append/read | "+reason);
      return;
   }
   if(journal.AppendDailyRearm(20261113,now_msc+5,9875.50,"   ","           ","       ",reason))
   {
      FailRiskJournalTest("daily rearm accepted missing operator attribution");
      return;
   }
   if(!journal.AppendDailyRearm(20261113,now_msc+5,9875.50,"owner-01","Manual recovery after equity and statement review","statement-2026-11-14",reason) ||
      journal.HasDailyLock(20261113) || !journal.HasDailyRearm(20261113) ||
      MathAbs(journal.DailyRearmEquity(20261113)-9875.50)>1e-8 ||
      journal.DailyRearmOperatorId(20261113)!="owner-01" ||
      journal.DailyRearmReason(20261113)!="Manual recovery after equity and statement review" ||
      journal.DailyRearmEvidenceReference(20261113)!="statement-2026-11-14")
   {
      FailRiskJournalTest("audited daily-rearm event append/read | "+reason);
      return;
   }
   if(!journal.AppendEmergencyStop(now_msc+6,reason) ||
      !journal.HasEmergencyStop())
   {
      FailRiskJournalTest("emergency-stop event append/read | "+reason);
      return;
   }
   if(journal.Count()!=5)
   {
      FailRiskJournalTest("record count did not equal four");
      return;
   }

   journal.Close();
   CVxRiskJournal replay;
   if(!replay.Init(test_login,test_server,reason))
   {
      FailRiskJournalTest("restart replay | "+reason);
      return;
   }
   if(replay.Count()!=5 || !replay.HasRequest(request_key) ||
      !replay.HasClose(close_key) || replay.HasDailyLock(20261113) ||
      !replay.HasDailyRearm(20261113) ||
      MathAbs(replay.DailyRearmEquity(20261113)-9875.50)>1e-8 ||
      replay.DailyRearmOperatorId(20261113)!="owner-01" ||
      replay.DailyRearmReason(20261113)!="Manual recovery after equity and statement review" ||
      replay.DailyRearmEvidenceReference(20261113)!="statement-2026-11-14" ||
      !replay.HasEmergencyStop())
   {
      FailRiskJournalTest("replayed records or idempotency index did not match");
      return;
   }

   PrintFormat("RISK JOURNAL RUNTIME TEST PASS | sequence=%I64d request_duplicate_blocked=true close_duplicate_blocked=true daily_lock_replay=true daily_rearm_replay=true emergency_stop_replay=true restart_replay=true synthetic_login=%I64d",
               replay.Count(),test_login);
   WriteRiskJournalResult("PASS | append, duplicate rejection, operator/reason/evidence-attributed daily rearm, restart replay, emergency-stop replay, checksum-chain replay");
   replay.Close();
}
