#include "../Include/Veltrix/RiskJournal.mqh"

#define RESULT_FILE "veltrix_risk_journal_failure_test.result"

ulong HashText64(const string value)
{
   ulong hash=14695981039346656037;
   for(int i=0;i<StringLen(value);i++)
   {
      hash^=(ulong)StringGetCharacter(value,i);
      hash*=1099511628211;
   }
   return hash;
}

string JournalName(const long login,const string server)
{
   return StringFormat("VELTRIX_XAUUSD_RISK_%I64d_%I64u.csv",login,HashText64(server));
}

void Result(const string value)
{
   int h=FileOpen(RESULT_FILE,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) { Print("RISK JOURNAL FAILURE TEST FAIL | result sentinel unavailable"); return; }
   FileWriteString(h,value);
   FileFlush(h);
   FileClose(h);
}

void OnStart()
{
   long test_login=910000000+(long)(GetTickCount64()%80000000);
   string lock_server="VELTRIX_JOURNAL_OPEN_LOCK_TEST";
   string corrupt_server="VELTRIX_JOURNAL_CORRUPTION_TEST";
   string reason="";
   string lock_file=JournalName(test_login,lock_server);

   // Hold an existing synthetic journal without share permissions. The
   // journal initializer must refuse to recreate or truncate that file.
   int held=FileOpen(lock_file,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(held==INVALID_HANDLE)
   {
      Result("FAIL | could not create synthetic locked journal");
      return;
   }
   CVxRiskJournal blocked;
   bool opened=blocked.Init(test_login,lock_server,reason);
   FileClose(held);
   if(opened || StringFind(reason,"Existing risk journal cannot be opened")<0)
   {
      FileDelete(lock_file,FILE_COMMON);
      Result("FAIL | existing locked journal was not rejected fail-closed: "+reason);
      return;
   }
   if(!FileDelete(lock_file,FILE_COMMON))
   {
      Result("FAIL | locked journal cleanup failed");
      return;
   }

   // Write one valid event, alter its first sequence byte, then ensure replay
   // rejects the damaged checksum-chain record rather than accepting it.
   string corrupt_file=JournalName(test_login,corrupt_server);
   CVxRiskJournal original;
   if(!original.Init(test_login,corrupt_server,reason))
   {
      Result("FAIL | corruption fixture initialization: "+reason);
      return;
   }
   if(!original.AppendRequest("CORRUPTION_FIXTURE",(long)TimeLocal()*1000,reason))
   {
      original.Close();
      FileDelete(corrupt_file,FILE_COMMON);
      Result("FAIL | corruption fixture append: "+reason);
      return;
   }
   original.Close();

   int raw=FileOpen(corrupt_file,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(raw==INVALID_HANDLE)
   {
      FileDelete(corrupt_file,FILE_COMMON);
      Result("FAIL | could not open synthetic journal for controlled corruption");
      return;
   }
   FileSeek(raw,0,SEEK_SET);
   uint written=FileWriteString(raw,"9");
   FileFlush(raw);
   FileClose(raw);
   if(written==0)
   {
      FileDelete(corrupt_file,FILE_COMMON);
      Result("FAIL | controlled journal corruption write failed");
      return;
   }

   CVxRiskJournal replay;
   reason="";
   bool replayed=replay.Init(test_login,corrupt_server,reason);
   if(replayed || StringFind(reason,"incomplete, malformed, or out-of-sequence record")<0)
   {
      replay.Close();
      FileDelete(corrupt_file,FILE_COMMON);
      Result("FAIL | corrupted journal was not rejected fail-closed: "+reason);
      return;
   }
   if(!FileDelete(corrupt_file,FILE_COMMON))
   {
      Result("FAIL | corrupted journal cleanup failed");
      return;
   }

   Print("RISK JOURNAL FAILURE TEST PASS | locked existing file rejected; corrupted journal replay rejected; synthetic cleanup complete");
   Result("PASS | existing journal write-lock rejection and checksum-chain corruption rejection; cleanup complete");
}
