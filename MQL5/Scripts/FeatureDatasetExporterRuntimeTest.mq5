#include "../Include/Veltrix/FeatureDatasetExporter.mqh"
#include "../Include/Veltrix/FeaturePipeline.mqh"

#define VX_RUNTIME_TEST_FILE "veltrix_dataset_export_runtime_test.csv"
#define VX_RUNTIME_BAD_HEADER_FILE "veltrix_dataset_export_bad_header.csv"
#define VX_RUNTIME_RESULT_FILE "veltrix_dataset_export_runtime_test.result"

void WriteRuntimeResult(const string value)
{
   int result_handle=FileOpen(VX_RUNTIME_RESULT_FILE,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(result_handle==INVALID_HANDLE)
   {
      Print("DATASET RUNTIME TEST FAIL | unable to write result sentinel");
      return;
   }
   FileWriteString(result_handle,value);
   FileFlush(result_handle);
   FileClose(result_handle);
}

void Fail(const string message)
{
   Print("DATASET RUNTIME TEST FAIL | ",message);
   WriteRuntimeResult("FAIL | "+message);
}

bool ReadField(const int handle,const string expected,const string label)
{
   string actual=FileReadString(handle);
   if(actual!=expected)
   {
      PrintFormat("DATASET RUNTIME TEST FAIL | %s expected='%s' actual='%s'",
                  label,expected,actual);
      return false;
   }
   return true;
}

void OnStart()
{
   FileDelete(VX_RUNTIME_TEST_FILE);
   FileDelete(VX_RUNTIME_RESULT_FILE);

   CVxFeatureDatasetExporter exporter;
   VxStrategySnapshot snapshot;
   long now=(long)TimeLocal()*1000;

   snapshot.symbol="XAUUSD";
   snapshot.quote_time_msc=now;
   snapshot.feature_window_start_msc=now-5000;
   snapshot.evaluation_time_msc=now+10;
   snapshot.bid=2000.0;
   snapshot.ask=2000.2;
   snapshot.momentum_bps=1.5;
   snapshot.realized_volatility_bps=2.5;
   snapshot.efficiency_ratio=0.6;
   snapshot.observations=10;

   string reason;
   if(!exporter.AppendSnapshot(VX_RUNTIME_TEST_FILE,"runtime-test-session",snapshot,reason))
   {
      Fail("first append | "+reason);
      return;
   }

   snapshot.quote_time_msc++;
   snapshot.feature_window_start_msc++;
   snapshot.evaluation_time_msc++;
   if(!exporter.AppendSnapshot(VX_RUNTIME_TEST_FILE,"runtime-test-session",snapshot,reason))
   {
      Fail("second append | "+reason);
      return;
   }

   VxStrategySnapshot invalid=snapshot;
   invalid.symbol="BTCUSD";
   if(exporter.AppendSnapshot(VX_RUNTIME_TEST_FILE,"runtime-test-session",invalid,reason))
   {
      Fail("invalid symbol was accepted");
      return;
   }

   if(exporter.AppendSnapshot("../unsafe.csv","runtime-test-session",snapshot,reason))
   {
      Fail("unsafe filename was accepted");
      return;
   }

   int bad_header_handle=FileOpen(VX_RUNTIME_BAD_HEADER_FILE,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(bad_header_handle==INVALID_HANDLE)
   {
      Fail("unable to create mismatched-header fixture");
      return;
   }
   FileWrite(bad_header_handle,"wrong_schema","wrong_fields");
   FileClose(bad_header_handle);
   if(exporter.AppendSnapshot(VX_RUNTIME_BAD_HEADER_FILE,"runtime-test-session",snapshot,reason))
   {
      FileDelete(VX_RUNTIME_BAD_HEADER_FILE);
      Fail("mismatched existing CSV header was accepted");
      return;
   }
   if(!FileDelete(VX_RUNTIME_BAD_HEADER_FILE) || FileIsExist(VX_RUNTIME_BAD_HEADER_FILE))
   {
      Fail("mismatched-header fixture cleanup failed");
      return;
   }

   int handle=FileOpen(VX_RUNTIME_TEST_FILE,FILE_READ|FILE_CSV|FILE_ANSI,',');
   if(handle==INVALID_HANDLE)
   {
      Fail("unable to reopen exported CSV");
      return;
   }

   string header[13]=
   {
      "schema_version","feature_version","source_id","symbol",
      "quote_time_msc","window_start_msc","evaluation_time_msc",
      "bid","ask","momentum_bps","realized_volatility_bps",
      "efficiency_ratio","observations"
   };
   bool ok=true;
   for(int i=0;i<13 && ok;i++)
      ok=ReadField(handle,header[i],"header");

   // Two rows, each containing thirteen fields. Values are checked at the
   // schema and identity boundaries; Python performs full numeric auditing.
   for(int row=0;row<2 && ok;row++)
   {
      ok=ReadField(handle,"1","schema_version") &&
         ReadField(handle,"1.0.0","feature_version") &&
         ReadField(handle,"runtime-test-session","source_id") &&
         ReadField(handle,"XAUUSD","symbol");
      for(int field=4;field<13 && ok;field++)
      {
         string value=FileReadString(handle);
         if(value=="")
         {
            PrintFormat("DATASET RUNTIME TEST FAIL | row %d field %d is empty",row,field);
            ok=false;
         }
      }
   }

   if(ok && !FileIsEnding(handle))
   {
      Print("DATASET RUNTIME TEST FAIL | unexpected extra CSV fields or rows");
      ok=false;
   }
   FileClose(handle);

   if(!ok)
   {
      FileDelete(VX_RUNTIME_TEST_FILE);
      Fail("CSV read-back mismatch");
      return;
   }

   if(!FileDelete(VX_RUNTIME_TEST_FILE) || FileIsExist(VX_RUNTIME_TEST_FILE))
   {
      Fail("CSV cleanup failed; test file remains in terminal Files sandbox");
      return;
   }

   FileDelete("veltrix_pipeline_runtime_test.csv");
   CVxFeaturePipeline pipeline;
   string pipeline_reason;
   if(!pipeline.Init("XAUUSD","runtime-pipeline-session",
                     "veltrix_pipeline_runtime_test.csv",
                     60000,2500,10,1000,pipeline_reason))
   {
      Fail("pipeline init | "+pipeline_reason);
      return;
   }

   int pipeline_rows=0;
   for(int i=0;i<=61;i++)
   {
      MqlTick synthetic;
      ZeroMemory(synthetic);
      synthetic.time_msc=now+(long)i*1000;
      synthetic.bid=2000.0+(double)i*0.01;
      synthetic.ask=synthetic.bid+0.2;
      bool row_written=false;
      if(!pipeline.ProcessQuote("XAUUSD",synthetic,row_written,pipeline_reason))
      {
         FileDelete("veltrix_pipeline_runtime_test.csv");
         Fail("pipeline quote processing | "+pipeline_reason);
         return;
      }
      if(row_written)
         pipeline_rows++;
   }
   if(pipeline.RowsWritten()!=2 || pipeline_rows!=2 ||
      !FileIsExist("veltrix_pipeline_runtime_test.csv"))
   {
      FileDelete("veltrix_pipeline_runtime_test.csv");
      Fail("pipeline did not export exactly two chronological warm-up-complete rows");
      return;
   }
   int pipeline_handle=FileOpen("veltrix_pipeline_runtime_test.csv",
                                FILE_READ|FILE_CSV|FILE_ANSI,',');
   if(pipeline_handle==INVALID_HANDLE)
   {
      FileDelete("veltrix_pipeline_runtime_test.csv");
      Fail("unable to reopen pipeline dataset");
      return;
   }
   string pipeline_header[13]=
   {
      "schema_version","feature_version","source_id","symbol",
      "quote_time_msc","window_start_msc","evaluation_time_msc",
      "bid","ask","momentum_bps","realized_volatility_bps",
      "efficiency_ratio","observations"
   };
   bool pipeline_ok=true;
   for(int h=0;h<13 && pipeline_ok;h++)
      pipeline_ok=ReadField(pipeline_handle,pipeline_header[h],"pipeline header");

   long previous_evaluation=0;
   for(int row=0;row<2 && pipeline_ok;row++)
   {
      pipeline_ok=ReadField(pipeline_handle,"1","pipeline schema") &&
                  ReadField(pipeline_handle,"1.0.0","pipeline feature version") &&
                  ReadField(pipeline_handle,"runtime-pipeline-session","pipeline source") &&
                  ReadField(pipeline_handle,"XAUUSD","pipeline symbol");
      long quote_time=StringToInteger(FileReadString(pipeline_handle));
      long window_start=StringToInteger(FileReadString(pipeline_handle));
      long evaluation_time=StringToInteger(FileReadString(pipeline_handle));
      if(window_start<=0 || window_start>quote_time ||
         quote_time>evaluation_time || evaluation_time<=previous_evaluation)
         pipeline_ok=false;
      previous_evaluation=evaluation_time;
      for(int field=7;field<13 && pipeline_ok;field++)
      {
         if(FileReadString(pipeline_handle)=="")
            pipeline_ok=false;
      }
   }
   if(pipeline_ok && !FileIsEnding(pipeline_handle))
      pipeline_ok=false;
   FileClose(pipeline_handle);
   if(!pipeline_ok)
   {
      FileDelete("veltrix_pipeline_runtime_test.csv");
      Fail("pipeline CSV read-back or chronology check failed");
      return;
   }

   if(!FileDelete("veltrix_pipeline_runtime_test.csv") ||
      FileIsExist("veltrix_pipeline_runtime_test.csv"))
   {
      Fail("pipeline dataset cleanup failed");
      return;
   }

   Print("DATASET RUNTIME TEST PASS | exporter and pipeline create, append, reject-invalid, read-back, cleanup");
   WriteRuntimeResult("PASS | exporter and pipeline create, append, reject-invalid, read-back, cleanup");
}
