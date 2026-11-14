//+------------------------------------------------------------------+
//| DailyLossOwnerRearm.mq5                                          |
//| Manual owner-operated daily-loss reactivation for VELTRIX.       |
//| DEMO-only; USD-only; no broker order APIs.                       |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

#include "../Include/Veltrix/RiskControls.mqh"

input long   InpExpectedDemoLogin=0;
input string InpExpectedDemoServer="";
input double InpVerifiedOriginalDeposit=0.0;
input bool   InpOriginalDepositEvidenceReviewed=false;
input string InpOwnerOperatorId="";
input string InpReactivationReason="";
input string InpReactivationEvidenceReference="";
input string InpConfirmationPhrase="";

void OnStart()
{
   if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
   { Print("VELTRIX DAILY REARM BLOCKED | DEMO account required"); return; }
   if(AccountInfoString(ACCOUNT_CURRENCY)!="USD")
   { Print("VELTRIX DAILY REARM BLOCKED | USD account currency required"); return; }
   if(InpExpectedDemoLogin<=0 || InpExpectedDemoServer=="")
   { Print("VELTRIX DAILY REARM BLOCKED | exact expected DEMO login/server are required"); return; }
   if((long)AccountInfoInteger(ACCOUNT_LOGIN)!=InpExpectedDemoLogin ||
      AccountInfoString(ACCOUNT_SERVER)!=InpExpectedDemoServer)
   { Print("VELTRIX DAILY REARM BLOCKED | connected account does not match owner-entered DEMO identity"); return; }
   if(!InpOriginalDepositEvidenceReviewed)
   { Print("VELTRIX DAILY REARM BLOCKED | owner must attest original-deposit evidence was reviewed"); return; }
   if(StringLen(InpReactivationEvidenceReference)<6)
   { Print("VELTRIX DAILY REARM BLOCKED | traceable evidence reference is required"); return; }
   if(InpConfirmationPhrase!="VELTRIX OWNER CONFIRM DAILY REACTIVATION")
   { Print("VELTRIX DAILY REARM BLOCKED | exact owner confirmation phrase is required"); return; }

   VxRiskControlConfig config;
   config.expected_demo_login=InpExpectedDemoLogin;
   config.expected_demo_server=InpExpectedDemoServer;
   config.risk_per_trade_percent=0.25;
   config.max_portfolio_risk_percent=0.50;
   config.max_daily_loss_percent=15.00;
   config.verified_original_deposit=InpVerifiedOriginalDeposit;
   config.original_deposit_verified=true;
   config.cooldown_seconds=0;
   config.max_consecutive_losses=0;

   CVxRiskControls controls;
   string reason="";
   if(!controls.Init(config,reason))
   { Print("VELTRIX DAILY REARM BLOCKED | risk-control initialization failed: ",reason); return; }

   long now_msc=(long)TimeTradeServer()*1000;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(now_msc<=0 || !MathIsValidNumber(equity) || equity<=0.0)
   { Print("VELTRIX DAILY REARM BLOCKED | verified server time/current equity unavailable"); return; }

   if(!controls.RearmDailyLossLock(equity,now_msc,InpOwnerOperatorId,
                                   InpReactivationReason,
                                   InpReactivationEvidenceReference,
                                   InpConfirmationPhrase,reason))
   { Print("VELTRIX DAILY REARM FAILED | ",reason); return; }

   Print("VELTRIX DAILY REARM SUCCESS | operator=",InpOwnerOperatorId,
         " | reason=",InpReactivationReason,
         " | evidence_ref=",InpReactivationEvidenceReference,
         " | new_daily_equity_baseline=",DoubleToString(equity,2),
         " | overall-loss lock and emergency stop were not cleared");
   Print("VELTRIX DAILY REARM NOTE | reinitialize/restart the EA to reload the audited daily baseline");
}
