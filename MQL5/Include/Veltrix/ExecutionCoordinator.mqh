//+------------------------------------------------------------------+
//| ExecutionCoordinator.mqh                                         |
//| Request lifecycle state machine only; no broker execution APIs.  |
//| This module cannot send, modify, or close orders.                 |
//+------------------------------------------------------------------+
#ifndef VELTRIX_EXECUTION_COORDINATOR_MQH
#define VELTRIX_EXECUTION_COORDINATOR_MQH

enum ENUM_VX_REQUEST_STATE
{
   VX_REQUEST_PREPARED=0,
   VX_REQUEST_SUBMITTING=1,
   VX_REQUEST_ACKNOWLEDGED=2,
   VX_REQUEST_PARTIALLY_FILLED=3,
   VX_REQUEST_FILLED=4,
   VX_REQUEST_REJECTED=5,
   VX_REQUEST_OUTCOME_UNKNOWN=6,
   VX_REQUEST_RECONCILING=7,
   VX_REQUEST_CANCELLED=8
};

struct VxExecutionRequest
{
   string request_id;
   string symbol;
   double requested_volume;
   double filled_volume;
   ulong broker_order_ticket;
   ulong first_deal_ticket;
   long broker_retcode;
   ENUM_VX_REQUEST_STATE state;
   long created_msc;
   long updated_msc;
   string last_reason;
};

class CVxExecutionCoordinator
{
private:
   VxExecutionRequest m_requests[];
   ulong m_seen_deals[];
   bool m_emergency_stop;
   bool m_connected;

   int FindRequest(const string request_id) const
   {
      for(int i=0;i<ArraySize(m_requests);i++)
         if(m_requests[i].request_id==request_id)
            return i;
      return -1;
   }

   bool DealAlreadySeen(const ulong deal_ticket) const
   {
      for(int i=0;i<ArraySize(m_seen_deals);i++)
         if(m_seen_deals[i]==deal_ticket)
            return true;
      return false;
   }

   bool RememberDeal(const ulong deal_ticket)
   {
      if(deal_ticket==0 || DealAlreadySeen(deal_ticket))
         return false;
      int size=ArraySize(m_seen_deals);
      if(ArrayResize(m_seen_deals,size+1)!=size+1)
         return false;
      m_seen_deals[size]=deal_ticket;
      return true;
   }

   bool IsTerminal(const ENUM_VX_REQUEST_STATE state) const
   {
      return (state==VX_REQUEST_FILLED ||
              state==VX_REQUEST_REJECTED ||
              state==VX_REQUEST_CANCELLED);
   }

public:
   CVxExecutionCoordinator(void)
   {
      m_emergency_stop=false;
      m_connected=true;
   }

   bool IsEmergencyStopped(void) const { return m_emergency_stop; }
   bool IsConnected(void) const { return m_connected; }
   int Count(void) const { return ArraySize(m_requests); }

   bool GetRequest(const int index,VxExecutionRequest &request) const
   {
      if(index<0 || index>=ArraySize(m_requests))
         return false;
      request=m_requests[index];
      return true;
   }

   // Records an approved intent. This does not submit anything to MT5.
   bool Prepare(const string request_id,const string symbol,
                const double requested_volume,const long now_msc,
                string &reason)
   {
      reason="";
      if(m_emergency_stop)
      {
         reason="Emergency stop is latched; new requests are blocked";
         return false;
      }
      if(!m_connected)
      {
         reason="Terminal is disconnected; new requests are blocked";
         return false;
      }
      if(request_id=="" || symbol=="" || requested_volume<=0.0 ||
         !MathIsValidNumber(requested_volume) || now_msc<=0)
      {
         reason="Invalid request identity, symbol, volume, or timestamp";
         return false;
      }
      if(FindRequest(request_id)>=0)
      {
         reason="Duplicate request identifier rejected";
         return false;
      }

      int size=ArraySize(m_requests);
      if(ArrayResize(m_requests,size+1)!=size+1)
      {
         reason="Execution request ledger allocation failed";
         return false;
      }
      m_requests[size].request_id=request_id;
      m_requests[size].symbol=symbol;
      m_requests[size].requested_volume=requested_volume;
      m_requests[size].filled_volume=0.0;
      m_requests[size].broker_order_ticket=0;
      m_requests[size].first_deal_ticket=0;
      m_requests[size].broker_retcode=0;
      m_requests[size].state=VX_REQUEST_PREPARED;
      m_requests[size].created_msc=now_msc;
      m_requests[size].updated_msc=now_msc;
      m_requests[size].last_reason="Intent recorded locally; no broker request sent";
      return true;
   }

   // Marks the hand-off boundary only. Caller must perform any future
   // broker operation separately and pass the real broker response back.
   bool MarkSubmitting(const string request_id,const long now_msc,
                       string &reason)
   {
      int index=FindRequest(request_id);
      if(index<0 || m_emergency_stop || !m_connected || now_msc<=0)
      {
         reason="Request not found, emergency stop active, disconnected, or invalid time";
         return false;
      }
      if(m_requests[index].state!=VX_REQUEST_PREPARED)
      {
         reason="Only a prepared request may cross the submission boundary";
         return false;
      }
      m_requests[index].state=VX_REQUEST_SUBMITTING;
      m_requests[index].updated_msc=now_msc;
      m_requests[index].last_reason="Submission hand-off recorded; no broker call is made by coordinator";
      reason="";
      return true;
   }

   bool RecordBrokerResponse(const string request_id,const ulong order_ticket,
                             const long retcode,const bool accepted,
                             const long now_msc,const string broker_message,
                             string &reason)
   {
      int index=FindRequest(request_id);
      if(index<0 || now_msc<=0)
      {
         reason="Unknown request identifier or invalid timestamp";
         return false;
      }
      if(m_requests[index].state==VX_REQUEST_FILLED)
      {
         m_requests[index].broker_retcode=retcode;
         if(order_ticket>0) m_requests[index].broker_order_ticket=order_ticket;
         m_requests[index].updated_msc=now_msc;
         reason="";
         return true;
      }
      if(m_requests[index].state!=VX_REQUEST_SUBMITTING &&
         m_requests[index].state!=VX_REQUEST_OUTCOME_UNKNOWN &&
         m_requests[index].state!=VX_REQUEST_RECONCILING)
      {
         reason="Broker response is not valid for the current request state";
         return false;
      }
      if(order_ticket==0 && accepted)
      {
         m_requests[index].state=VX_REQUEST_OUTCOME_UNKNOWN;
         m_requests[index].last_reason="Broker response claims acceptance without an order ticket; reconcile before retry";
         m_requests[index].broker_retcode=retcode;
         m_requests[index].updated_msc=now_msc;
         reason="Accepted response missing broker order ticket";
         return false;
      }

      m_requests[index].broker_retcode=retcode;
      m_requests[index].broker_order_ticket=order_ticket;
      m_requests[index].updated_msc=now_msc;
      if(accepted)
      {
         m_requests[index].state=(m_requests[index].filled_volume>0.0 ?
            VX_REQUEST_PARTIALLY_FILLED : VX_REQUEST_ACKNOWLEDGED);
         m_requests[index].last_reason=(broker_message=="" ?
            "Broker acknowledgement recorded" : broker_message);
      }
      else if(m_requests[index].filled_volume>0.0)
      {
         m_requests[index].state=VX_REQUEST_PARTIALLY_FILLED;
         m_requests[index].last_reason="Broker rejected remaining request after a partial fill; reconcile filled exposure";
      }
      else
      {
         m_requests[index].state=VX_REQUEST_OUTCOME_UNKNOWN;
         m_requests[index].last_reason=(broker_message=="" ?
            "Broker rejection received; reconcile history before treating request as terminal" :
            broker_message+"; reconcile history before treating request as terminal");
      }
      reason="";
      return true;
   }

   bool RecordFill(const string request_id,const ulong deal_ticket,
                   const double deal_volume,const long now_msc,
                   string &reason)
   {
      int index=FindRequest(request_id);
      if(index<0 || deal_ticket==0 || deal_volume<=0.0 ||
         !MathIsValidNumber(deal_volume) || now_msc<=0)
      {
         reason="Invalid fill identity, volume, or timestamp";
         return false;
      }
      if(m_requests[index].state==VX_REQUEST_PREPARED)
      {
         reason="Fill cannot be applied to an unsubmitted request";
         return false;
      }
      if(DealAlreadySeen(deal_ticket))
      {
         reason="Duplicate deal update ignored";
         return false;
      }
      double next_volume=m_requests[index].filled_volume+deal_volume;
      bool terminal_conflict=(m_requests[index].state==VX_REQUEST_REJECTED ||
                              m_requests[index].state==VX_REQUEST_CANCELLED ||
                              m_requests[index].state==VX_REQUEST_FILLED);
      double tolerance=MathMax(1e-8,m_requests[index].requested_volume*1e-6);
      if(next_volume>m_requests[index].requested_volume+tolerance)
      {
         reason="Cumulative fill exceeds requested volume; reconciliation required";
         m_requests[index].state=VX_REQUEST_OUTCOME_UNKNOWN;
         m_requests[index].updated_msc=now_msc;
         m_requests[index].last_reason=reason;
         return false;
      }
      if(!RememberDeal(deal_ticket))
      {
         reason="Deal deduplication ledger could not record this deal";
         return false;
      }

      m_requests[index].filled_volume=next_volume;
      if(m_requests[index].first_deal_ticket==0)
         m_requests[index].first_deal_ticket=deal_ticket;
      m_requests[index].updated_msc=now_msc;
      if(terminal_conflict)
      {
         m_requests[index].state=VX_REQUEST_OUTCOME_UNKNOWN;
         m_requests[index].last_reason="Late or contradictory deal conflicts with a terminal request state; broker reconciliation required";
      }
      else if(next_volume+tolerance>=m_requests[index].requested_volume)
      {
         m_requests[index].filled_volume=m_requests[index].requested_volume;
         m_requests[index].state=VX_REQUEST_FILLED;
         m_requests[index].last_reason="Cumulative unique broker deals satisfy requested volume";
      }
      else
      {
         m_requests[index].state=VX_REQUEST_PARTIALLY_FILLED;
         m_requests[index].last_reason="Partial broker fill recorded; remaining volume is unresolved";
      }
      reason="";
      return true;
   }

   bool MarkOutcomeUnknown(const string request_id,const long now_msc,
                           const string reason)
   {
      int index=FindRequest(request_id);
      if(index<0 || now_msc<=0 || IsTerminal(m_requests[index].state))
         return false;
      m_requests[index].state=VX_REQUEST_OUTCOME_UNKNOWN;
      m_requests[index].updated_msc=now_msc;
      m_requests[index].last_reason=(reason=="" ?
         "Broker outcome uncertain; reconcile before any retry" : reason);
      return true;
   }

   bool BeginReconciliation(const string request_id,const long now_msc)
   {
      int index=FindRequest(request_id);
      if(index<0 || now_msc<=0 ||
         (m_requests[index].state!=VX_REQUEST_OUTCOME_UNKNOWN &&
          m_requests[index].state!=VX_REQUEST_PARTIALLY_FILLED))
         return false;
      m_requests[index].state=VX_REQUEST_RECONCILING;
      m_requests[index].updated_msc=now_msc;
      m_requests[index].last_reason="Broker reconciliation in progress; retry remains blocked";
      return true;
   }

   bool ResolveFromBroker(const string request_id,const double broker_confirmed_volume,
                          const bool broker_confirms_terminal_rejection,
                          const long now_msc,const string reason)
   {
      int index=FindRequest(request_id);
      if(index<0 || now_msc<=0 ||
         m_requests[index].state!=VX_REQUEST_RECONCILING ||
         broker_confirmed_volume<0.0 || !MathIsValidNumber(broker_confirmed_volume))
         return false;

      double tolerance=MathMax(1e-8,m_requests[index].requested_volume*1e-6);
      if(broker_confirmed_volume>m_requests[index].requested_volume+tolerance)
      {
         m_requests[index].state=VX_REQUEST_OUTCOME_UNKNOWN;
         m_requests[index].last_reason="Broker-reconciled volume exceeds request; manual investigation required";
         m_requests[index].updated_msc=now_msc;
         return false;
      }
      m_requests[index].filled_volume=broker_confirmed_volume;
      m_requests[index].updated_msc=now_msc;
      if(broker_confirmed_volume+tolerance>=m_requests[index].requested_volume)
      {
         m_requests[index].filled_volume=m_requests[index].requested_volume;
         m_requests[index].state=VX_REQUEST_FILLED;
         m_requests[index].last_reason="Full requested volume confirmed by broker reconciliation";
      }
      else if(broker_confirms_terminal_rejection && broker_confirmed_volume<=tolerance)
      {
         m_requests[index].state=VX_REQUEST_REJECTED;
         m_requests[index].last_reason=(reason=="" ?
            "Broker confirmed terminal rejection with no fill" : reason);
      }
      else if(broker_confirmed_volume>tolerance)
      {
         m_requests[index].state=VX_REQUEST_PARTIALLY_FILLED;
         m_requests[index].last_reason=(reason=="" ?
            "Broker confirms partial exposure; remainder remains unsubmitted" : reason);
      }
      else
      {
         m_requests[index].state=VX_REQUEST_OUTCOME_UNKNOWN;
         m_requests[index].last_reason=(reason=="" ?
            "Broker confirms no fill but not a terminal rejection; keep outcome unknown" : reason);
      }
      return true;
   }

   void SetDisconnected(const long now_msc)
   {
      m_connected=false;
      for(int i=0;i<ArraySize(m_requests);i++)
      {
         if(m_requests[i].state==VX_REQUEST_PREPARED)
         {
            m_requests[i].state=VX_REQUEST_CANCELLED;
            m_requests[i].updated_msc=now_msc;
            m_requests[i].last_reason="Terminal disconnected before submission; prepared intent cancelled locally";
         }
         else if(!IsTerminal(m_requests[i].state))
         {
            m_requests[i].state=VX_REQUEST_OUTCOME_UNKNOWN;
            m_requests[i].updated_msc=now_msc;
            m_requests[i].last_reason="Terminal disconnected; broker outcome must be reconciled before retry";
         }
      }
   }

   void SetReconnected(void)
   {
      m_connected=true;
      // Reconnection alone is not proof of request outcome.
   }

   void LatchEmergencyStop(const long now_msc,const string reason)
   {
      m_emergency_stop=true;
      for(int i=0;i<ArraySize(m_requests);i++)
      {
         if(m_requests[i].state==VX_REQUEST_PREPARED)
         {
            m_requests[i].state=VX_REQUEST_CANCELLED;
            m_requests[i].updated_msc=now_msc;
            m_requests[i].last_reason="Emergency stop latched before submission; prepared intent cancelled locally";
         }
         else if(!IsTerminal(m_requests[i].state))
         {
            m_requests[i].state=VX_REQUEST_OUTCOME_UNKNOWN;
            m_requests[i].updated_msc=now_msc;
            m_requests[i].last_reason=(reason=="" ?
               "Emergency stop latched; in-flight broker outcome requires reconciliation" : reason);
         }
      }
   }

   // Deliberately no reset method: clearing an emergency stop requires
   // a separately reviewed operator/session-control procedure.
};

#endif
