//+------------------------------------------------------------------+
//| BrokerReconciler.mqh                                             |
//| Read-only broker snapshot and history reconciliation.            |
//| No order submission, modification, or closure APIs.               |
//+------------------------------------------------------------------+
#ifndef VELTRIX_BROKER_RECONCILER_MQH
#define VELTRIX_BROKER_RECONCILER_MQH

#include "PositionRegistry.mqh"

enum ENUM_VX_RECONCILE_STATUS
{
   VX_RECONCILE_LIVE_VERIFIED=0,
   VX_RECONCILE_LIVE_PARTIAL_OR_VOLUME_CHANGED=1,
   VX_RECONCILE_PROTECTION_FAILURE=2,
   VX_RECONCILE_CLOSED_CONFIRMED=3,
   VX_RECONCILE_CLOSE_HISTORY_INCOMPLETE=4,
   VX_RECONCILE_UNKNOWN=5
};

struct VxReconcileRow
{
   long identifier;
   ulong registry_ticket;
   ulong broker_ticket;
   string symbol;
   ENUM_VX_POSITION_STATE registry_state;
   ENUM_VX_RECONCILE_STATUS status;
   bool broker_position_found;
   double expected_volume;
   double live_volume;
   double stop_loss;
   double take_profit;
   double confirmed_exit_volume;
   int closing_deal_count;
   string reason;
};

struct VxReconcileSummary
{
   int scanned;
   int live_verified;
   int volume_mismatches;
   int protection_failures;
   int closed_confirmed;
   int incomplete_history;
   int unknown;
};

class CVxBrokerReconciler
{
private:
   VxReconcileRow m_rows[];

   bool FindLivePosition(const long identifier,const string expected_symbol,
                         string &actual_symbol,ulong &ticket,double &volume,
                         double &stop_loss,double &take_profit,
                         double &current_price,long &position_type)
   {
      actual_symbol="";
      ticket=0;
      volume=0.0;
      stop_loss=0.0;
      take_profit=0.0;
      current_price=0.0;
      position_type=-1;

      for(int i=PositionsTotal()-1;i>=0;i--)
      {
         ulong candidate=PositionGetTicket(i);
         if(candidate==0 || !PositionSelectByTicket(candidate))
            continue;
         if(PositionGetInteger(POSITION_IDENTIFIER)!=identifier)
            continue;

         actual_symbol=PositionGetString(POSITION_SYMBOL);
         ticket=candidate;
         volume=PositionGetDouble(POSITION_VOLUME);
         stop_loss=PositionGetDouble(POSITION_SL);
         take_profit=PositionGetDouble(POSITION_TP);
         current_price=PositionGetDouble(POSITION_PRICE_CURRENT);
         position_type=PositionGetInteger(POSITION_TYPE);
         return true;
      }
      return false;
   }

   bool ReadClosingDeals(const VxPositionRecord &record,double &exit_volume,
                         int &deal_count)
   {
      exit_volume=0.0;
      deal_count=0;
      datetime from_time=(datetime)(record.opened_msc/1000)-60;
      datetime to_time=TimeCurrent()+60;
      if(from_time<=0 || to_time<from_time || !HistorySelect(from_time,to_time))
         return false;

      for(int i=0;i<HistoryDealsTotal();i++)
      {
         ulong deal=HistoryDealGetTicket(i);
         if(deal==0 || HistoryDealGetInteger(deal,DEAL_POSITION_ID)!=record.identifier)
            continue;
         if(HistoryDealGetString(deal,DEAL_SYMBOL)!=record.symbol)
            return false;

         long entry=HistoryDealGetInteger(deal,DEAL_ENTRY);
         if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY)
            continue;

         double volume=HistoryDealGetDouble(deal,DEAL_VOLUME);
         if(!MathIsValidNumber(volume) || volume<=0.0)
            return false;
         exit_volume+=volume;
         if(!MathIsValidNumber(exit_volume))
            return false;
         deal_count++;
      }
      return true;
   }

   bool HasValidProtectiveStop(const long position_type,
                               const double current_price,
                               const double stop_loss)
   {
      if(!MathIsValidNumber(current_price) ||
         !MathIsValidNumber(stop_loss) ||
         stop_loss<=0.0 || current_price<=0.0)
         return false;
      if(position_type==POSITION_TYPE_BUY)
         return stop_loss<current_price;
      if(position_type==POSITION_TYPE_SELL)
         return stop_loss>current_price;
      return false;
   }

public:
   int Count(void) const { return ArraySize(m_rows); }

   bool GetRow(const int index,VxReconcileRow &row) const
   {
      if(index<0 || index>=ArraySize(m_rows))
         return false;
      row=m_rows[index];
      return true;
   }

   bool Reconcile(CVxPositionRegistry &registry,VxReconcileSummary &summary)
   {
      ArrayResize(m_rows,0);
      summary.scanned=0;
      summary.live_verified=0;
      summary.volume_mismatches=0;
      summary.protection_failures=0;
      summary.closed_confirmed=0;
      summary.incomplete_history=0;
      summary.unknown=0;

      for(int i=0;i<registry.Count();i++)
      {
         VxPositionRecord record;
         if(!registry.GetAt(i,record) || record.state==VX_POSITION_CLOSED)
            continue;

         int row_index=ArraySize(m_rows);
         if(ArrayResize(m_rows,row_index+1)!=row_index+1)
            return false;

         VxReconcileRow row;
         row.identifier=record.identifier;
         row.registry_ticket=record.ticket;
         row.broker_ticket=0;
         row.symbol=record.symbol;
         row.registry_state=record.state;
         row.status=VX_RECONCILE_UNKNOWN;
         row.broker_position_found=false;
         row.expected_volume=record.volume;
         row.live_volume=0.0;
         row.stop_loss=0.0;
         row.take_profit=0.0;
         row.confirmed_exit_volume=0.0;
         row.closing_deal_count=0;
         row.reason="Broker state has not yet been reconciled";

         string live_symbol="";
         ulong live_ticket=0;
         double live_volume=0.0;
         double stop_loss=0.0;
         double take_profit=0.0;
         double current_price=0.0;
         long position_type=-1;

         if(FindLivePosition(record.identifier,record.symbol,live_symbol,
                             live_ticket,live_volume,stop_loss,take_profit,
                             current_price,position_type))
         {
            row.broker_position_found=true;
            if(live_symbol!=record.symbol)
            {
               row.status=VX_RECONCILE_UNKNOWN;
               row.reason="Live broker position symbol differs from registered XAUUSD contract";
               registry.MarkUnknown(record.identifier,row.reason);
               summary.unknown++;
               m_rows[row_index]=row;
               summary.scanned++;
               continue;
            }
            row.broker_ticket=live_ticket;
            row.live_volume=live_volume;
            row.stop_loss=stop_loss;
            row.take_profit=take_profit;

            if(!MathIsValidNumber(live_volume) || live_volume<=0.0)
            {
               row.status=VX_RECONCILE_UNKNOWN;
               row.reason="Live broker position volume is invalid or non-finite";
               registry.MarkUnknown(record.identifier,row.reason);
               summary.unknown++;
            }
            else if(!HasValidProtectiveStop(position_type,current_price,stop_loss))
            {
               row.status=VX_RECONCILE_PROTECTION_FAILURE;
               row.reason="Live broker position has no valid protective stop";
               registry.MarkProtectionFailure(record.identifier,row.reason);
               summary.protection_failures++;
            }
            else if(MathAbs(live_volume-record.volume)>MathMax(1e-8,record.volume*1e-6))
            {
               row.status=VX_RECONCILE_LIVE_PARTIAL_OR_VOLUME_CHANGED;
               row.reason="Live position volume differs from registered volume; inspect partial fills or reductions";
               registry.MarkUnknown(record.identifier,row.reason);
               summary.volume_mismatches++;
            }
            else
            {
               row.status=VX_RECONCILE_LIVE_VERIFIED;
               row.reason="Broker identifier, ticket, volume, and protective stop verified";
               registry.MarkLiveVerified(record.identifier,live_ticket,row.reason);
               summary.live_verified++;
            }
         }
         else
         {
            bool history_ok=ReadClosingDeals(record,row.confirmed_exit_volume,
                                             row.closing_deal_count);
            double tolerance=MathMax(1e-8,record.volume*1e-6);

            if(history_ok && row.confirmed_exit_volume+tolerance>=record.volume &&
               row.closing_deal_count>0)
            {
               row.status=VX_RECONCILE_CLOSED_CONFIRMED;
               row.reason="No live position; cumulative closing deals cover registered volume";
               registry.ConfirmClosed(record.identifier,true,row.reason);
               summary.closed_confirmed++;
            }
            else if(history_ok && row.confirmed_exit_volume>tolerance)
            {
               row.status=VX_RECONCILE_CLOSE_HISTORY_INCOMPLETE;
               row.reason="Closing deals exist but do not account for registered position volume";
               registry.MarkUnknown(record.identifier,row.reason);
               summary.incomplete_history++;
            }
            else
            {
               row.status=VX_RECONCILE_UNKNOWN;
               row.reason=(history_ok ?
                  "Position absent and no matching closing deal was found" :
                  "Broker history unavailable; position outcome remains unknown");
               registry.MarkUnknown(record.identifier,row.reason);
               summary.unknown++;
            }
         }

         m_rows[row_index]=row;
         summary.scanned++;
      }
      return true;
   }
};

#endif
