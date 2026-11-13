//+------------------------------------------------------------------+
//| RiskAllocator.mqh                                                |
//| Pure, fail-closed risk sizing and portfolio allocation.          |
//| Does not query accounts or submit/modify/close orders.           |
//+------------------------------------------------------------------+
#ifndef VELTRIX_RISK_ALLOCATOR_MQH
#define VELTRIX_RISK_ALLOCATOR_MQH

struct VxRiskRequest
{
   double equity;
   double risk_percent;
   double stop_distance_price;
   double tick_size;
   double tick_value_loss;
   double volume_min;
   double volume_max;
   double volume_step;
   double current_open_risk_money;
   double max_portfolio_risk_percent;
   int    open_positions; // Observability only; no position-count ceiling.
};

struct VxRiskDecision
{
   bool   approved;
   double volume;
   double risk_budget_money;
   double portfolio_capacity_money;
   double estimated_loss_money;
   string reason;
};

int VxVolumeDigits(const double step)
{
   for(int digits=0; digits<=8; digits++)
   {
      if(MathAbs(NormalizeDouble(step,digits)-step)<1e-10)
         return digits;
   }
   return 8;
}

bool VxCalculateRiskVolume(const VxRiskRequest &request,
                           VxRiskDecision &decision)
{
   decision.approved=false;
   decision.volume=0.0;
   decision.risk_budget_money=0.0;
   decision.portfolio_capacity_money=0.0;
   decision.estimated_loss_money=0.0;
   decision.reason="";

   // Comparisons alone do not reject NaN: every numeric input must be finite
   // before it participates in any risk or volume arithmetic.
   if(!MathIsValidNumber(request.equity) ||
      !MathIsValidNumber(request.risk_percent) ||
      !MathIsValidNumber(request.stop_distance_price) ||
      !MathIsValidNumber(request.tick_size) ||
      !MathIsValidNumber(request.tick_value_loss) ||
      !MathIsValidNumber(request.volume_min) ||
      !MathIsValidNumber(request.volume_max) ||
      !MathIsValidNumber(request.volume_step) ||
      !MathIsValidNumber(request.current_open_risk_money) ||
      !MathIsValidNumber(request.max_portfolio_risk_percent))
   {
      decision.reason="Non-finite numeric input; risk sizing rejected";
      return false;
   }

   if(request.equity<=0.0 || request.risk_percent<=0.0 ||
      request.stop_distance_price<=0.0 || request.tick_size<=0.0 ||
      request.tick_value_loss<=0.0 || request.volume_min<=0.0 ||
      request.volume_max<request.volume_min || request.volume_step<=0.0)
   {
      decision.reason="Invalid equity, risk, stop, tick economics, or volume specification";
      return false;
   }

   if(request.max_portfolio_risk_percent<=0.0 ||
      request.current_open_risk_money<0.0 ||
      request.open_positions<0)
   {
      decision.reason="Invalid portfolio limits or current exposure";
      return false;
   }

   // Position count is intentionally uncapped. Aggregate open risk and
   // broker margin are the binding portfolio constraints.

   double loss_per_lot=(request.stop_distance_price/request.tick_size)*
                       request.tick_value_loss;
   if(!MathIsValidNumber(loss_per_lot) || loss_per_lot<=0.0)
   {
      decision.reason="Calculated loss per lot is invalid";
      return false;
   }

   decision.risk_budget_money=request.equity*
                              request.risk_percent/100.0;
   double portfolio_limit=request.equity*
                           request.max_portfolio_risk_percent/100.0;
   decision.portfolio_capacity_money=portfolio_limit-
                                     request.current_open_risk_money;

   if(!MathIsValidNumber(decision.risk_budget_money) ||
      !MathIsValidNumber(portfolio_limit) ||
      !MathIsValidNumber(decision.portfolio_capacity_money))
   {
      decision.reason="Non-finite derived risk budget; risk sizing rejected";
      return false;
   }

   if(decision.risk_budget_money<=0.0 ||
      decision.portfolio_capacity_money<=0.0)
   {
      decision.reason="No remaining risk capacity";
      return false;
   }

   double allowed_loss=MathMin(decision.risk_budget_money,
                               decision.portfolio_capacity_money);
   if(!MathIsValidNumber(allowed_loss) || allowed_loss<=0.0)
   {
      decision.reason="Allowed loss budget is invalid";
      return false;
   }

   double raw_volume=allowed_loss/loss_per_lot;
   if(!MathIsValidNumber(raw_volume) || raw_volume<=0.0)
   {
      decision.reason="Calculated raw volume is invalid";
      return false;
   }
   raw_volume=MathMin(raw_volume,request.volume_max);

   // Round down only. Never force a trade by rounding up to minimum volume.
   double steps=MathFloor(raw_volume/request.volume_step+1e-10);
   double volume=NormalizeDouble(steps*request.volume_step,
                                 VxVolumeDigits(request.volume_step));
   if(!MathIsValidNumber(volume))
   {
      decision.reason="Rounded volume is invalid";
      return false;
   }

   if(volume<request.volume_min)
   {
      decision.reason="Risk-sized volume is below broker minimum; trade skipped";
      return false;
   }

   double estimated_loss=volume*loss_per_lot;
   if(!MathIsValidNumber(estimated_loss))
   {
      decision.reason="Estimated loss is invalid";
      return false;
   }

   // Defend against floating-point boundary overshoot.
   while(estimated_loss>allowed_loss+1e-8 && volume>=request.volume_min)
   {
      volume=NormalizeDouble(volume-request.volume_step,
                             VxVolumeDigits(request.volume_step));
      estimated_loss=volume*loss_per_lot;
      if(!MathIsValidNumber(volume) || !MathIsValidNumber(estimated_loss))
      {
         decision.reason="Risk correction produced invalid numeric values";
         return false;
      }
   }

   if(volume<request.volume_min || estimated_loss>allowed_loss+1e-8)
   {
      decision.reason="No broker-valid volume fits the available risk budget";
      return false;
   }

   decision.approved=true;
   decision.volume=volume;
   decision.estimated_loss_money=estimated_loss;
   decision.reason="Risk and portfolio limits passed; broker preflight still required";
   return true;
}

#endif
