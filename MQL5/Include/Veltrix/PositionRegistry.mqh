//+------------------------------------------------------------------+
//| PositionRegistry.mqh                                             |
//| Per-position lifecycle ledger; no trade or order APIs.           |
//| Broker disappearance is UNKNOWN until a close deal is verified. |
//+------------------------------------------------------------------+
#ifndef VELTRIX_POSITION_REGISTRY_MQH
#define VELTRIX_POSITION_REGISTRY_MQH

enum ENUM_VX_POSITION_STATE
{
   VX_POSITION_OPEN=0,
   VX_POSITION_CLOSE_DUE=1,
   VX_POSITION_CLOSE_PENDING=2,
   VX_POSITION_UNKNOWN=3,
   VX_POSITION_PROTECTION_FAILURE=4,
   VX_POSITION_CLOSED=5
};

struct VxPositionRecord
{
   ulong  ticket;
   long   identifier;
   string symbol;
   double volume;
   long   opened_msc;
   int    hold_seconds;
   long   close_due_msc;
   ENUM_VX_POSITION_STATE state;
   string last_reason;
};

class CVxPositionRegistry
{
private:
   VxPositionRecord m_records[];

   int FindByIdentifier(const long identifier) const
   {
      for(int i=0;i<ArraySize(m_records);i++)
         if(m_records[i].identifier==identifier)
            return i;
      return -1;
   }

   int FindByTicket(const ulong ticket) const
   {
      for(int i=0;i<ArraySize(m_records);i++)
         if(m_records[i].ticket==ticket)
            return i;
      return -1;
   }

public:
   int Count(void) const
   {
      return ArraySize(m_records);
   }

   int ActiveCount(void) const
   {
      int count=0;
      for(int i=0;i<ArraySize(m_records);i++)
      {
         if(m_records[i].state!=VX_POSITION_CLOSED)
            count++;
      }
      return count;
   }

   bool RegisterConfirmedOpen(const ulong ticket,
                              const long identifier,
                              const string symbol,
                              const double volume,
                              const long opened_msc,
                              const int hold_seconds,
                              string &reason)
   {
      reason="";
      if(ticket==0 || identifier<=0 || symbol=="" || volume<=0.0 ||
         opened_msc<=0 || hold_seconds<10 || hold_seconds>60)
      {
         reason="Invalid confirmed position data or hold duration outside 10-60 seconds";
         return false;
      }

      if(FindByIdentifier(identifier)>=0 || FindByTicket(ticket)>=0)
      {
         reason="Position ticket or identifier is already registered";
         return false;
      }

      int size=ArraySize(m_records);
      if(ArrayResize(m_records,size+1)!=size+1)
      {
         reason="Position registry allocation failed";
         return false;
      }

      m_records[size].ticket=ticket;
      m_records[size].identifier=identifier;
      m_records[size].symbol=symbol;
      m_records[size].volume=volume;
      m_records[size].opened_msc=opened_msc;
      m_records[size].hold_seconds=hold_seconds;
      m_records[size].close_due_msc=opened_msc+(long)hold_seconds*1000;
      m_records[size].state=VX_POSITION_OPEN;
      m_records[size].last_reason="Broker-confirmed open position registered";
      return true;
   }

   int EvaluateCloseDeadlines(const long now_msc)
   {
      if(now_msc<=0)
         return 0;

      int due=0;
      for(int i=0;i<ArraySize(m_records);i++)
      {
         if(m_records[i].state==VX_POSITION_OPEN &&
            now_msc>=m_records[i].close_due_msc)
         {
            m_records[i].state=VX_POSITION_CLOSE_DUE;
            m_records[i].last_reason="Configured holding deadline reached; close action required";
            due++;
         }
      }
      return due;
   }

   bool MarkClosePending(const long identifier,const string reason)
   {
      int index=FindByIdentifier(identifier);
      if(index<0 || m_records[index].state!=VX_POSITION_CLOSE_DUE)
         return false;

      m_records[index].state=VX_POSITION_CLOSE_PENDING;
      m_records[index].last_reason=(reason=="" ?
         "Close request handed to execution layer; broker confirmation pending" : reason);
      return true;
   }

   bool MarkUnknown(const long identifier,const string reason)
   {
      int index=FindByIdentifier(identifier);
      if(index<0 || m_records[index].state==VX_POSITION_CLOSED)
         return false;

      m_records[index].state=VX_POSITION_UNKNOWN;
      m_records[index].last_reason=(reason=="" ?
         "Broker state uncertain; reconcile before retrying" : reason);
      return true;
   }

   bool MarkProtectionFailure(const long identifier,const string reason)
   {
      int index=FindByIdentifier(identifier);
      if(index<0 || m_records[index].state==VX_POSITION_CLOSED)
         return false;

      m_records[index].state=VX_POSITION_PROTECTION_FAILURE;
      m_records[index].last_reason=(reason=="" ?
         "Protective stop state is not verified" : reason);
      return true;
   }

   bool ConfirmClosed(const long identifier,
                      const bool broker_close_deal_confirmed,
                      const string reason)
   {
      int index=FindByIdentifier(identifier);
      if(index<0 || !broker_close_deal_confirmed)
         return false;

      m_records[index].state=VX_POSITION_CLOSED;
      m_records[index].last_reason=(reason=="" ?
         "Closing deal confirmed in broker history" : reason);
      return true;
   }

   bool GetAt(const int index,VxPositionRecord &record) const
   {
      if(index<0 || index>=ArraySize(m_records))
         return false;
      record=m_records[index];
      return true;
   }
};

#endif
