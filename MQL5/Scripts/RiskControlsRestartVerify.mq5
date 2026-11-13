#include "../Include/Veltrix/RiskControls.mqh"

#define RESULT_FILE "veltrix_risk_restart_verify.result"
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
   if(h==INVALID_HANDLE) { Print("RISK RESTART VERIFY FAIL | result sentinel unavailable"); return; }
   FileWriteString(h,value);
   FileFlush(h);
   FileClose(h);
}

bool VerifyAcrossProcessRestart(string &reason)
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
   if(!controls.Init(config,reason))
      return false;
   if(!controls.IsEmergencyStopped())
   { reason="emergency stop did not survive terminal process restart"; return false; }
   if(!controls.IsDailyLossLocked())
   { reason="daily loss lock did not survive terminal process restart"; return false; }
   return true;
}

void Cleanup(void)
{
   string suffix=Suffix();
   string journal=StringFormat("VELTRIX_XAUUSD_RISK_%I64d_%I64u.csv",
                               (long)TEST_LOGIN,HashText64(TEST_SERVER));
   FileDelete(journal,FILE_COMMON);
   string keys[8];
   keys[0]="VX_ESTOP_"+suffix; keys[1]="VX_DAY_"+suffix;
   keys[2]="VX_EQ_"+suffix; keys[3]="VX_LOCK_"+suffix;
   keys[4]="VX_LS_"+suffix; keys[5]="VX_CD_"+suffix;
   keys[6]="VX_CSUM_"+suffix; keys[7]="VX_LOCKTX_"+suffix;
   for(int i=0;i<8;i++) GlobalVariableDel(keys[i]);
}

void OnStart()
{
   string reason="";
   if(!VerifyAcrossProcessRestart(reason))
   {
      Result("FAIL | restart persistence verification: "+reason);
      return;
   }
   Cleanup();
   Print("RISK PROCESS RESTART TEST PASS | emergency-stop and daily-lock survived a new terminal process");
   Result("PASS | terminal process restart restored emergency-stop and daily-lock state; cleanup complete");
}
