//+------------------------------------------------------------------+
//| ExecutionGuard.mqh                                               |
//| Demo-only execution preflight; never submits or modifies orders. |
//+------------------------------------------------------------------+
#ifndef VELTRIX_EXECUTION_GUARD_MQH
#define VELTRIX_EXECUTION_GUARD_MQH

enum ENUM_VX_INTENT_SIDE
{
   VX_SIDE_BUY=0,
   VX_SIDE_SELL=1
};

struct VxExecutionIntent
{
   long expected_demo_login;
   string expected_demo_server;
   string symbol;
   ENUM_VX_INTENT_SIDE side;
   double volume;
   double requested_price;
   double stop_loss;
   double take_profit;
   ulong  max_quote_age_ms;
   double max_spread_points;
   double margin_reserve_money;
};

struct VxExecutionDecision
{
   bool   approved;
   double validated_price;
   double spread_points;
   double estimated_margin;
   string reason;
};

class CVxExecutionGuard
{
private:
   bool IsVolumeStepValid(const double volume,
                          const double minimum,
                          const double maximum,
                          const double step)
   {
      if(!MathIsValidNumber(volume) || !MathIsValidNumber(minimum) ||
         !MathIsValidNumber(maximum) || !MathIsValidNumber(step) ||
         volume<minimum-1e-9 || volume>maximum+1e-9 || step<=0.0)
         return false;
      double steps=volume/step;
      return MathIsValidNumber(steps) &&
             MathAbs(steps-MathRound(steps))<1e-7;
   }

public:
   bool ValidateDemoIntent(const VxExecutionIntent &intent,
                           VxExecutionDecision &decision)
   {
      decision.approved=false;
      decision.validated_price=0.0;
      decision.spread_points=0.0;
      decision.estimated_margin=0.0;
      decision.reason="";

      if(intent.expected_demo_login<=0 || intent.expected_demo_server=="" ||
         intent.symbol=="" ||
         (intent.side!=VX_SIDE_BUY && intent.side!=VX_SIDE_SELL) ||
         !MathIsValidNumber(intent.volume) || intent.volume<=0.0 ||
         !MathIsValidNumber(intent.requested_price) ||
         !MathIsValidNumber(intent.stop_loss) ||
         !MathIsValidNumber(intent.take_profit) ||
         intent.max_quote_age_ms==0 ||
         !MathIsValidNumber(intent.max_spread_points) ||
         intent.max_spread_points<=0.0 ||
         !MathIsValidNumber(intent.margin_reserve_money) ||
         intent.margin_reserve_money<0.0)
      {
         decision.reason="Intent contains invalid or non-finite fields";
         return false;
      }

      // This initial release is intentionally restricted to demo accounts.
      if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
      {
         decision.reason="Account is not a verified DEMO account";
         return false;
      }
      if((long)AccountInfoInteger(ACCOUNT_LOGIN)!=intent.expected_demo_login ||
         AccountInfoString(ACCOUNT_SERVER)!=intent.expected_demo_server)
      {
         decision.reason="Connected DEMO login or server does not exactly match configured identity";
         return false;
      }

      if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      {
         decision.reason="Hedging account required for independently managed positions";
         return false;
      }

      if(!TerminalInfoInteger(TERMINAL_CONNECTED) ||
         !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ||
         !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
         !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) ||
         !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
      {
         decision.reason="Terminal, program, or account trading permission is disabled";
         return false;
      }

      if(!SymbolSelect(intent.symbol,true))
      {
         decision.reason="Requested broker symbol is unavailable";
         return false;
      }
      string normalized_symbol=intent.symbol;
      StringToUpper(normalized_symbol);
      string base_currency="",profit_currency="";
      if(StringLen(normalized_symbol)<6 ||
         StringSubstr(normalized_symbol,0,6)!="XAUUSD" ||
         !SymbolInfoString(intent.symbol,SYMBOL_CURRENCY_BASE,base_currency) ||
         !SymbolInfoString(intent.symbol,SYMBOL_CURRENCY_PROFIT,profit_currency))
      {
         decision.reason="Only a broker-verified XAUUSD contract is permitted";
         return false;
      }
      StringToUpper(base_currency);
      StringToUpper(profit_currency);
      if(base_currency!="XAU" || profit_currency!="USD")
      {
         decision.reason="Symbol metadata does not confirm XAU base and USD profit currencies";
         return false;
      }

      long trade_mode=0;
      long stops_level=0;
      if(!SymbolInfoInteger(intent.symbol,SYMBOL_TRADE_MODE,trade_mode) ||
         !SymbolInfoInteger(intent.symbol,SYMBOL_TRADE_STOPS_LEVEL,stops_level))
      {
         decision.reason="Broker trade mode or stop-level metadata unavailable";
         return false;
      }

      if(trade_mode==SYMBOL_TRADE_MODE_DISABLED ||
         trade_mode==SYMBOL_TRADE_MODE_CLOSEONLY)
      {
         decision.reason="Broker symbol is disabled or close-only";
         return false;
      }
      if(intent.side==VX_SIDE_BUY && trade_mode==SYMBOL_TRADE_MODE_SHORTONLY)
      {
         decision.reason="Broker symbol currently permits short positions only";
         return false;
      }
      if(intent.side==VX_SIDE_SELL && trade_mode==SYMBOL_TRADE_MODE_LONGONLY)
      {
         decision.reason="Broker symbol currently permits long positions only";
         return false;
      }

      MqlTick tick;
      if(!SymbolInfoTick(intent.symbol,tick) ||
         !MathIsValidNumber(tick.bid) || !MathIsValidNumber(tick.ask) ||
         tick.bid<=0.0 || tick.ask<=0.0 || tick.ask<tick.bid ||
         tick.time_msc<=0)
      {
         decision.reason="Current broker quote is missing or invalid";
         return false;
      }

      datetime server_now=TimeTradeServer();
      double point=SymbolInfoDouble(intent.symbol,SYMBOL_POINT);
      int digits=(int)SymbolInfoInteger(intent.symbol,SYMBOL_DIGITS);
      if(server_now<=0 || !MathIsValidNumber(point) || point<=0.0 || digits<0)
      {
         decision.reason="Broker time or symbol price precision is unavailable";
         return false;
      }

      long age=(long)server_now*1000-tick.time_msc+999;
      if(age<0 || (ulong)age>intent.max_quote_age_ms)
      {
         decision.reason="Quote is stale or its timestamp is ahead of broker time";
         return false;
      }

      decision.spread_points=(tick.ask-tick.bid)/point;
      if(!MathIsValidNumber(decision.spread_points) ||
         decision.spread_points<=0.0 ||
         decision.spread_points>intent.max_spread_points)
      {
         decision.reason="Current spread exceeds the intent's validated maximum";
         return false;
      }

      double price=(intent.side==VX_SIDE_BUY ? tick.ask : tick.bid);
      if(intent.requested_price>0.0 &&
         MathAbs(intent.requested_price-price)>point*2.0)
      {
         decision.reason="Intent price drifted more than two points from live quote";
         return false;
      }

      if(intent.stop_loss<=0.0)
      {
         decision.reason="A protective stop loss is mandatory";
         return false;
      }

      double stop_distance=(intent.side==VX_SIDE_BUY ?
                            price-intent.stop_loss :
                            intent.stop_loss-price);
      if(!MathIsValidNumber(stop_distance) || stop_distance<=0.0 ||
         stop_distance+point*1e-6<(double)stops_level*point)
      {
         decision.reason="Protective stop is on the wrong side or violates broker stop distance";
         return false;
      }

      if(intent.take_profit>0.0)
      {
         bool valid_target=(intent.side==VX_SIDE_BUY ?
                            intent.take_profit>price :
                            intent.take_profit<price);
         if(!valid_target)
         {
            decision.reason="Take-profit is on the wrong side of the live price";
            return false;
         }
      }

      double minimum=SymbolInfoDouble(intent.symbol,SYMBOL_VOLUME_MIN);
      double maximum=SymbolInfoDouble(intent.symbol,SYMBOL_VOLUME_MAX);
      double step=SymbolInfoDouble(intent.symbol,SYMBOL_VOLUME_STEP);
      if(!IsVolumeStepValid(intent.volume,minimum,maximum,step))
      {
         decision.reason="Volume violates broker min/max/step constraints";
         return false;
      }

      ENUM_ORDER_TYPE order_type=(intent.side==VX_SIDE_BUY ?
                                  ORDER_TYPE_BUY : ORDER_TYPE_SELL);
      double margin=0.0;
      if(!OrderCalcMargin(order_type,intent.symbol,intent.volume,price,margin) ||
         !MathIsValidNumber(margin) || margin<=0.0)
      {
         decision.reason="Broker margin estimate failed; refusing intent";
         return false;
      }

      double free_margin=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      if(!MathIsValidNumber(free_margin) || free_margin<=0.0 ||
         free_margin-margin<intent.margin_reserve_money)
      {
         decision.reason="Free margin would fall below the required reserve";
         return false;
      }

      decision.validated_price=NormalizeDouble(price,digits);
      decision.estimated_margin=margin;
      decision.approved=true;
      decision.reason="Demo preflight passed; this module does not submit orders";
      return true;
   }
};

#endif
