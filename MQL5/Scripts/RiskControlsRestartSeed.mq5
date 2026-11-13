#include "../Include/Veltrix/RiskControls.mqh"

#define RESULT_FILE "veltrix_risk_restart_seed.result"
#define TEST_LOGIN 900000007
#define TEST_SERVER "VELTRIX_PHASE7_PROCESS_RESTART_TEST"

ulong HashText64(const string value)
{
   ulong hash=14695981039346656037;
   for(int i=0;i<StringLen(value);i++)
   {
      hash^=(ulong)StringGetCharacter(value,i);
      hash*=1099511628211;
   }
   return hash;
}

string Suffix(void)
{
   return StringFormat("%I64d_%I64u",(long)TEST_LOGIN,HashText64(TEST_SERVER));
}

void Result(const string value)
{
   int h=FileOpen(RESULT_FILE,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) { Print("RISK RESTART SEED FAIL | result sentinel unavailable"); return; }
   FileWriteString(h,value);
   FileFlush(h);
   FileClose(h);
}

bool PrepareCleanState(void)
{
   string suffix=Suffix();
   string journal=StringFormat("VELTRIX_XAUUSD_RISK_%I64d_%I64u.csv",
                               (long)TEST_LOGIN,HashText64(TEST_SERVER));
   if(FileIsExist(journal,FILE_COMMON) && !FileDelete(journal,FILE_COMMON))
      return false;
   string keys[8];
   keys[0]="VX_ESTOP_"+suffix; keys[1]="VX_DAY_"+suffix;
   keys[2]="VX_EQ_"+suffix; keys[3]="VX_LOCK_"+suffix;
   keys[4]="VX_LS_"+suffix; keys[5]="VX_CD_"+suffix;
   keys[6]="VX_CSUM_"+suffix; keys[7]="VX_LOCKTX_"+suffix;
   for(int i=0;i<8;i++) GlobalVariableDel(keys[i]);
   return true;
}

bool SeedEmergencyStop(string &reason)
{
   VxRiskControlConfig config;
   config.expected_demo_login=TEST_LOGIN;
   config.expected_demo_server=TEST_SERVER;
   config.risk_per_trade_percent=0.10;
   config.max_portfolio_risk_percent=0.25;
   config.max_daily_loss_percent=1.00;
   config.max_positions=1;
   config.cooldown_seconds=30;
   config.max_consecutive_losses=3;
   CVxRiskControls controls;
   if(!controls.Init(config,reason)) return false;
   return controls.LatchEmergencyStop(reason);
}

bool AppendSyntheticDailyLock(string &reason)
{
   CVxRiskJournal journal;
   if(!journal.Init(TEST_LOGIN,TEST_SERVER,reason)) return false;
   bool ok=journal.AppendDailyLock(20261113,(long)TimeLocal()*1000,1.0,reason);
   journal.Close();
   return ok;
}

void OnStart()
{
   if(!PrepareCleanState())
   {
      Result("FAIL | unable to clear prior synthetic test state");
      return;
   }
   string reason="";
   if(!SeedEmergencyStop(reason))
   {
      Result("FAIL | emergency-stop seed: "+reason);
      return;
   }
   if(!AppendSyntheticDailyLock(reason))
   {
      Result("FAIL | daily-lock seed: "+reason);
      return;
   }
   Print("RISK RESTART SEED PASS | synthetic identity only; terminal shutdown required before verification");
   Result("PASS | emergency-stop and daily-lock persisted before terminal process restart");
}
