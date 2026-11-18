//+------------------------------------------------------------------+
//| OverallLossOwnerRearm.mq5                                        |
//| Manual owner-operated reactivation for the VELTRIX overall lock. |
//| No order APIs; DEMO-only; USD account required.                  |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

#include "../Include/Veltrix/OverallAccountLossGuard.mqh"

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
   { Print("VELTRIX REARM BLOCKED | DEMO account required"); return; }
   if(AccountInfoString(ACCOUNT_CURRENCY)!="USD")
   { Print("VELTRIX REARM BLOCKED | USD account currency required"); return; }
   if((long)AccountInfoInteger(ACCOUNT_LOGIN)!=InpExpectedDemoLogin ||
      AccountInfoString(ACCOUNT_SERVER)!=InpExpectedDemoServer)
   { Print("VELTRIX REARM BLOCKED | connected account does not match owner-entered DEMO identity"); return; }
   if(!InpOriginalDepositEvidenceReviewed)
   { Print("VELTRIX REARM BLOCKED | owner must attest that original-deposit evidence was reviewed"); return; }
   if(StringLen(InpReactivationEvidenceReference)<6)
   { Print("VELTRIX REARM BLOCKED | a traceable evidence reference (statement ID/date or secure record reference) is required"); return; }
   string audited_reason=InpReactivationReason+" | evidence_ref="+InpReactivationEvidenceReference;
   if(StringLen(audited_reason)>240)
   { Print("VELTRIX REARM BLOCKED | reason and evidence reference exceed audit field limit"); return; }

   CVxOverallAccountLossGuard guard;
   string reason="";
   if(!guard.Init(InpExpectedDemoLogin,InpExpectedDemoServer,
                  InpVerifiedOriginalDeposit,true,reason))
   { Print("VELTRIX REARM BLOCKED | guard initialization failed: ",reason); return; }
   if(!guard.IsLocked())
   { Print("VELTRIX REARM BLOCKED | no active overall-loss lock exists"); return; }

   if(!guard.Rearm(InpOwnerOperatorId,audited_reason,
                   InpConfirmationPhrase,reason))
   { Print("VELTRIX REARM FAILED | ",reason); return; }

   Print("VELTRIX OVERALL-LOSS REARM SUCCESS | operator=",InpOwnerOperatorId,
         " | reason=",InpReactivationReason,
         " | evidence_ref=",InpReactivationEvidenceReference,
         " | immutable original-deposit baseline retained");
}
