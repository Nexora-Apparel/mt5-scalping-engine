//+------------------------------------------------------------------+
//| PortfolioExposureLedger.mqh                                      |
//| Per-position aggregate stop-risk and margin ledger.               |
//| No broker queries and no order submission/modification APIs.     |
//+------------------------------------------------------------------+
#ifndef VELTRIX_PORTFOLIO_EXPOSURE_LEDGER_MQH
#define VELTRIX_PORTFOLIO_EXPOSURE_LEDGER_MQH

enum ENUM_VX_EXPOSURE_STATE
{
   VX_EXPOSURE_OPEN=0,
   VX_EXPOSURE_CLOSE_PENDING=1,
   VX_EXPOSURE_UNKNOWN=2,
   VX_EXPOSURE_PROTECTION_FAILURE=3,
   VX_EXPOSURE_CLOSED=4
};

struct VxPortfolioExposure
{
   long identifier;
   ulong ticket;
   double stop_risk_money;
   double margin_money;
   ENUM_VX_EXPOSURE_STATE state;
};

class CVxPortfolioExposureLedger
{
private:
   VxPortfolioExposure m_items[];

   int Find(const long identifier) const
   {
      for(int i=0;i<ArraySize(m_items);i++)
         if(m_items[i].identifier==identifier)
            return i;
      return -1;
   }

public:
   int Count(void) const
   {
      return ArraySize(m_items);
   }

   int ActiveCount(void) const
   {
      int count=0;
      for(int i=0;i<ArraySize(m_items);i++)
         if(m_items[i].state!=VX_EXPOSURE_CLOSED)
            count++;
      return count;
   }

   bool Register(const long identifier,const ulong ticket,
                 const double stop_risk_money,const double margin_money,
                 string &reason)
   {
      reason="";
      if(identifier<=0 || ticket==0 ||
         !MathIsValidNumber(stop_risk_money) || stop_risk_money<=0.0 ||
         !MathIsValidNumber(margin_money) || margin_money<=0.0)
      {
         reason="Exposure identity, stop risk, or margin is invalid";
         return false;
      }
      if(Find(identifier)>=0)
      {
         reason="Duplicate position identifier rejected";
         return false;
      }
      int size=ArraySize(m_items);
      if(ArrayResize(m_items,size+1)!=size+1)
      {
         reason="Exposure ledger allocation failed";
         return false;
      }
      m_items[size].identifier=identifier;
      m_items[size].ticket=ticket;
      m_items[size].stop_risk_money=stop_risk_money;
      m_items[size].margin_money=margin_money;
      m_items[size].state=VX_EXPOSURE_OPEN;
      return true;
   }

   bool MarkClosePending(const long identifier)
   {
      int index=Find(identifier);
      if(index<0 || m_items[index].state==VX_EXPOSURE_CLOSED)
         return false;
      m_items[index].state=VX_EXPOSURE_CLOSE_PENDING;
      return true;
   }

   bool MarkUnknown(const long identifier)
   {
      int index=Find(identifier);
      if(index<0 || m_items[index].state==VX_EXPOSURE_CLOSED)
         return false;
      m_items[index].state=VX_EXPOSURE_UNKNOWN;
      return true;
   }

   bool MarkProtectionFailure(const long identifier)
   {
      int index=Find(identifier);
      if(index<0 || m_items[index].state==VX_EXPOSURE_CLOSED)
         return false;
      m_items[index].state=VX_EXPOSURE_PROTECTION_FAILURE;
      return true;
   }

   bool UpdateStopRisk(const long identifier,const double new_stop_risk_money)
   {
      int index=Find(identifier);
      if(index<0 || m_items[index].state==VX_EXPOSURE_CLOSED ||
         !MathIsValidNumber(new_stop_risk_money) || new_stop_risk_money<=0.0)
         return false;
      // A stop may reduce risk, but this ledger never authorizes widening it.
      if(new_stop_risk_money>m_items[index].stop_risk_money+1e-8)
         return false;
      m_items[index].stop_risk_money=new_stop_risk_money;
      return true;
   }

   bool ConfirmClosed(const long identifier,const bool broker_close_confirmed)
   {
      int index=Find(identifier);
      if(index<0 || !broker_close_confirmed)
         return false;
      m_items[index].state=VX_EXPOSURE_CLOSED;
      return true;
   }

   double AggregateOpenRiskMoney(void) const
   {
      double total=0.0;
      for(int i=0;i<ArraySize(m_items);i++)
         if(m_items[i].state!=VX_EXPOSURE_CLOSED)
            total+=m_items[i].stop_risk_money;
      return total;
   }

   double AggregateMarginMoney(void) const
   {
      double total=0.0;
      for(int i=0;i<ArraySize(m_items);i++)
         if(m_items[i].state!=VX_EXPOSURE_CLOSED)
            total+=m_items[i].margin_money;
      return total;
   }

   bool GetAt(const int index,VxPortfolioExposure &item) const
   {
      if(index<0 || index>=ArraySize(m_items))
         return false;
      item=m_items[index];
      return true;
   }
};

#endif
