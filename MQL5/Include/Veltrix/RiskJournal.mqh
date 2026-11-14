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
   string m_daily_lock_keys[];
   string m_daily_rearm_days[];
   double m_daily_rearm_equity[];
   bool m_emergency_stop;
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

   bool RemoveValue(string &items[],const string value)
   {
      for(int i=0;i<ArraySize(items);i++)
      {
         if(items[i]!=value) continue;
         int size=ArraySize(items);
         for(int j=i;j<size-1;j++) items[j]=items[j+1];
         ArrayResize(items,size-1);
         return true;
      }
      return false;
   }

   bool AddDailyRearm(const string day_key,const double equity)
   {
      if(day_key=="" || !MathIsValidNumber(equity) || equity<=0.0) return false;
      int size=ArraySize(m_daily_rearm_days);
      if(ArrayResize(m_daily_rearm_days,size+1)!=size+1) return false;
      if(ArrayResize(m_daily_rearm_equity,size+1)!=size+1)
      { ArrayResize(m_daily_rearm_days,size); return false; }
      m_daily_rearm_days[size]=day_key;
      m_daily_rearm_equity[size]=equity;
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
      ArrayResize(m_daily_lock_keys,0);
      ArrayResize(m_daily_rearm_days,0);
      ArrayResize(m_daily_rearm_equity,0);
      m_emergency_stop=false;
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
            (event_type!="REQUEST" && event_type!="CLOSE" &&
             event_type!="ESTOP" && event_type!="DAILY_LOCK" &&
             event_type!="DAILY_REARM"))
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
         else if(event_type=="CLOSE")
         {
            if(!AddUnique(m_close_keys,key))
            { reason="Risk journal contains a duplicate closing-deal key"; return false; }
         }
         else if(event_type=="ESTOP")
         {
            if(key!="LATCHED" || m_emergency_stop)
            { reason="Risk journal contains an invalid or duplicate emergency-stop event"; return false; }
            m_emergency_stop=true;
         }
         else if(event_type=="DAILY_LOCK")
         {
            if(!AddUnique(m_daily_lock_keys,key))
            { reason="Risk journal contains a duplicate daily-lock event"; return false; }
         }
         else if(event_type=="DAILY_REARM")
         {
            if(!Contains(m_daily_lock_keys,key))
            { reason="Risk journal contains a daily rearm without a preceding active daily lock"; return false; }
            if(!AddDailyRearm(key,value))
            { reason="Risk journal contains an invalid daily-rearm event"; return false; }
            RemoveValue(m_daily_lock_keys,key);
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
         (event_type!="REQUEST" && event_type!="CLOSE" &&
          event_type!="ESTOP" && event_type!="DAILY_LOCK" &&
          event_type!="DAILY_REARM"))
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
      else if(event_type=="CLOSE")
      {
         if(!AddUnique(m_close_keys,key))
         { reason="Risk journal in-memory close index allocation failed"; return false; }
      }
      else if(event_type=="ESTOP")
      {
         if(key!="LATCHED" || m_emergency_stop)
         { reason="Risk journal emergency-stop state is already latched"; return false; }
         m_emergency_stop=true;
      }
      else if(event_type=="DAILY_LOCK")
      {
         if(!AddUnique(m_daily_lock_keys,key))
         { reason="Risk journal in-memory daily-lock index allocation failed"; return false; }
      }
      else if(event_type=="DAILY_REARM")
      {
         if(!AddDailyRearm(key,value))
         { reason="Risk journal in-memory daily-rearm index allocation failed"; return false; }
         RemoveValue(m_daily_lock_keys,key);
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
      m_emergency_stop=false;
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
         if(file_existed)
         { reason="Existing risk journal cannot be opened; refusing to recreate or truncate it"; return false; }
         ResetLastError();
         int create_handle=FileOpen(m_filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
         if(create_handle==INVALID_HANDLE)
         { reason="Could not create account-scoped risk journal in MT5 Common Files"; return false; }
         FileFlush(create_handle);
         FileClose(create_handle);
         m_created_new=true;
         m_handle=FileOpen(m_filename,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,',');
      }
      else if(!file_existed)
      {
         // FILE_WRITE may create the file during the first READ|WRITE open.
         // Record that fact here; otherwise risk controls misclassify a new,
         // empty journal as an old journal with missing persistent state.
         m_created_new=true;
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

   bool HasEmergencyStop(void) const { return m_emergency_stop; }

   bool HasDailyLock(const long day_key) const
   {
      return Contains(m_daily_lock_keys,StringFormat("%I64d",day_key));
   }

   bool HasDailyRearm(const long day_key) const
   {
      string key=StringFormat("%I64d",day_key);
      for(int i=ArraySize(m_daily_rearm_days)-1;i>=0;i--)
         if(m_daily_rearm_days[i]==key) return true;
      return false;
   }

   double DailyRearmEquity(const long day_key) const
   {
      string key=StringFormat("%I64d",day_key);
      for(int i=ArraySize(m_daily_rearm_days)-1;i>=0;i--)
         if(m_daily_rearm_days[i]==key) return m_daily_rearm_equity[i];
      return 0.0;
   }

   int ActiveDailyLockCount(void) const { return ArraySize(m_daily_lock_keys); }

   long ActiveDailyLockDay(void) const
   {
      if(ArraySize(m_daily_lock_keys)<=0) return 0;
      return (long)StringToInteger(m_daily_lock_keys[ArraySize(m_daily_lock_keys)-1]);
   }

   bool HasAnyDailyRearm(void) const { return (ArraySize(m_daily_rearm_days)>0); }

   double LatestDailyRearmEquity(void) const
   {
      int size=ArraySize(m_daily_rearm_equity);
      return (size>0 ? m_daily_rearm_equity[size-1] : 0.0);
   }

   bool AppendEmergencyStop(const long timestamp_msc,string &reason)
   {
      if(m_emergency_stop)
      { reason=""; return true; }
      return Append("ESTOP","LATCHED",timestamp_msc,1.0,reason);
   }

   bool AppendDailyLock(const long day_key,const long timestamp_msc,
                        const double loss_percent,string &reason)
   {
      if(day_key<=0)
      { reason="Daily-lock journal key is invalid"; return false; }
      string key=StringFormat("%I64d",day_key);
      if(Contains(m_daily_lock_keys,key))
      { reason=""; return true; }
      return Append("DAILY_LOCK",key,timestamp_msc,loss_percent,reason);
   }

   bool AppendDailyRearm(const long day_key,const long timestamp_msc,
                         const double new_starting_equity,string &reason)
   {
      if(day_key<=0 || timestamp_msc<=0 || !MathIsValidNumber(new_starting_equity) || new_starting_equity<=0.0)
      { reason="Daily-rearm event requires a valid day, timestamp, and verified equity"; return false; }
      string key=StringFormat("%I64d",day_key);
      if(!Contains(m_daily_lock_keys,key))
      { reason="Daily loss is not locked for the requested server day"; return false; }
      return Append("DAILY_REARM",key,timestamp_msc,new_starting_equity,reason);
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
