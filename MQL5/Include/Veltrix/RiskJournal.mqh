//+------------------------------------------------------------------+
//| RiskJournal.mqh                                                  |
//| Append-only, checksum-chained DEMO risk/idempotency journal.     |
//| Uses the MT5 Common Files area; never stores credentials.        |
//+------------------------------------------------------------------+
#ifndef VELTRIX_RISK_JOURNAL_MQH
#define VELTRIX_RISK_JOURNAL_MQH

class CVxRiskJournal
{
private:
   int m_handle;
   string m_filename;
   long m_sequence;
   string m_previous_hash;
   string m_request_keys[];
   string m_close_keys[];
   bool m_initialized;
   bool m_created_new;

   ulong Hash64(const string value) const
   {
      // FNV-1a 64-bit; unsigned overflow is intentional.
      ulong hash=14695981039346656037;
      for(int i=0;i<StringLen(value);i++)
      {
         hash^=(ulong)StringGetCharacter(value,i);
         hash*=1099511628211;
      }
      return hash;
   }

   string HashText(const string value) const
   {
      return StringFormat("%I64u",Hash64(value));
   }

   bool Contains(const string &items[],const string value) const
   {
      for(int i=0;i<ArraySize(items);i++)
         if(items[i]==value)
            return true;
      return false;
   }

   bool AddUnique(string &items[],const string value)
   {
      if(value=="" || Contains(items,value))
         return false;
      int size=ArraySize(items);
      if(ArrayResize(items,size+1)!=size+1)
         return false;
      items[size]=value;
      return true;
   }

   string BuildPayload(const long sequence,const string event_type,
                       const string key,const long timestamp_msc,
                       const double value,const string previous_hash) const
   {
      return StringFormat("%I64d|%s|%s|%I64d|%.17g|%s",
                          sequence,event_type,key,timestamp_msc,value,previous_hash);
   }

   bool Replay(string &reason)
   {
      reason="";
      m_sequence=0;
      m_previous_hash="0";
      ArrayResize(m_request_keys,0);
      ArrayResize(m_close_keys,0);
      FileSeek(m_handle,0,SEEK_SET);
      while(!FileIsEnding(m_handle))
      {
         double sequence_number=FileReadNumber(m_handle);
         if(FileIsEnding(m_handle) && sequence_number==0.0)
            break;
         string event_type=FileReadString(m_handle);
         string key=FileReadString(m_handle);
         double timestamp_number=FileReadNumber(m_handle);
         double value=FileReadNumber(m_handle);
         string previous_hash=FileReadString(m_handle);
         string checksum=FileReadString(m_handle);
         if(!MathIsValidNumber(sequence_number) ||
            !MathIsValidNumber(timestamp_number) ||
            !MathIsValidNumber(value) ||
            sequence_number!=(double)(m_sequence+1) ||
            timestamp_number<=0.0 || key=="" ||
            previous_hash!=m_previous_hash ||
            (event_type!="REQUEST" && event_type!="CLOSE"))
         {
            reason="Risk journal contains an incomplete, malformed, or out-of-sequence record";
            return false;
         }
         long sequence=(long)sequence_number;
         long timestamp_msc=(long)timestamp_number;
         string payload=BuildPayload(sequence,event_type,key,timestamp_msc,value,previous_hash);
         if(checksum!=HashText(payload))
         {
            reason="Risk journal checksum chain is invalid";
            return false;
         }
         if(event_type=="REQUEST")
         {
            if(!AddUnique(m_request_keys,key))
            { reason="Risk journal contains a duplicate request key"; return false; }
         }
         else
         {
            if(!AddUnique(m_close_keys,key))
            { reason="Risk journal contains a duplicate closing-deal key"; return false; }
         }
         m_sequence=sequence;
         m_previous_hash=checksum;
      }
      FileSeek(m_handle,0,SEEK_END);
      return true;
   }

   bool Append(const string event_type,const string key,
               const long timestamp_msc,const double value,string &reason)
   {
      reason="";
      if(!m_initialized || m_handle==INVALID_HANDLE ||
         key=="" || timestamp_msc<=0 || !MathIsValidNumber(value) ||
         (event_type!="REQUEST" && event_type!="CLOSE"))
      { reason="Risk journal is not initialized or append fields are invalid"; return false; }
      if(event_type=="REQUEST" && Contains(m_request_keys,key))
      { reason="Duplicate request identifier rejected by durable journal"; return false; }
      if(event_type=="CLOSE" && Contains(m_close_keys,key))
      { reason="Duplicate verified closing deal rejected by durable journal"; return false; }

      long next_sequence=m_sequence+1;
      string payload=BuildPayload(next_sequence,event_type,key,timestamp_msc,value,m_previous_hash);
      string checksum=HashText(payload);
      FileSeek(m_handle,0,SEEK_END);
      ResetLastError();
      uint written=FileWrite(m_handle,(double)next_sequence,event_type,key,
                             (double)timestamp_msc,value,m_previous_hash,checksum);
      if(written==0)
      { reason="Risk journal append failed; transaction must remain locked"; return false; }
      ResetLastError();
      FileFlush(m_handle);
      if(GetLastError()!=0)
      { reason="Risk journal flush reported an error; transaction must remain locked"; return false; }

      if(event_type=="REQUEST")
      {
         if(!AddUnique(m_request_keys,key))
         { reason="Risk journal in-memory request index allocation failed"; return false; }
      }
      else
      {
         if(!AddUnique(m_close_keys,key))
         { reason="Risk journal in-memory close index allocation failed"; return false; }
      }
      m_sequence=next_sequence;
      m_previous_hash=checksum;
      return true;
   }

public:
   CVxRiskJournal(void)
   {
      m_handle=INVALID_HANDLE;
      m_filename="";
      m_sequence=0;
      m_previous_hash="0";
      m_initialized=false;
      m_created_new=false;
   }

   ~CVxRiskJournal(void)
   {
      Close();
   }

   bool Init(const long demo_login,const string demo_server,
             string &reason)
   {
      reason="";
      if(demo_login<=0 || demo_server=="")
      { reason="Risk journal requires exact DEMO account identity"; return false; }
      if(m_handle!=INVALID_HANDLE)
         Close();
      m_created_new=false;
      string server_material=demo_server;
      ulong server_hash=Hash64(server_material);
      m_filename=StringFormat("VELTRIX_XAUUSD_RISK_%I64d_%I64u.csv",
                              demo_login,server_hash);
      bool file_existed=FileIsExist(m_filename,FILE_COMMON);
      m_handle=FileOpen(m_filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,',');
      if(m_handle==INVALID_HANDLE)
      {
         ResetLastError();
         int create_handle=FileOpen(m_filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
         if(create_handle==INVALID_HANDLE)
         { reason="Could not create account-scoped risk journal in MT5 Common Files"; return false; }
         FileFlush(create_handle);
         FileClose(create_handle);
         m_created_new=true;
         m_handle=FileOpen(m_filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,',');
      }
      if(m_handle==INVALID_HANDLE)
      { reason="Could not open account-scoped risk journal"; return false; }
      if(!Replay(reason))
      {
         Close();
         return false;
      }
      m_initialized=true;
      return true;
   }

   void Close(void)
   {
      if(m_handle!=INVALID_HANDLE)
      {
         FileFlush(m_handle);
         FileClose(m_handle);
      }
      m_handle=INVALID_HANDLE;
      m_initialized=false;
   }

   bool HasRequest(const string key) const
   {
      return Contains(m_request_keys,key);
   }

   bool HasClose(const string key) const
   {
      return Contains(m_close_keys,key);
   }

   bool AppendRequest(const string key,const long timestamp_msc,string &reason)
   {
      return Append("REQUEST",key,timestamp_msc,0.0,reason);
   }

   bool AppendClose(const string key,const long timestamp_msc,
                    const double net_profit,string &reason)
   {
      return Append("CLOSE",key,timestamp_msc,net_profit,reason);
   }

   long Count(void) const { return m_sequence; }
   bool IsInitialized(void) const { return m_initialized; }
   bool WasCreatedNew(void) const { return m_created_new; }
};

#endif
