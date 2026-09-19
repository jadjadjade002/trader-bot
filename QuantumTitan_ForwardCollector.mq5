#property strict
#property version "2.00"
#property description "No-trade XAUUSD M1 observed forward collector."

const string SCHEMA_VERSION="1";
const string COLLECTOR_VERSION="2.00";
const string RUN_ID="FWD_20260909_4W";
const string PLANNED_END_ISO="2026-10-07T15:00:00";
const datetime PLANNED_END=D'2026.10.07 15:00:00';
const int HEALTH_SECONDS=300;
const string DATA_DIR="QTForward\\";
const string BAR_HEADER="schema_version,collector_version,run_id,symbol,time_broker_epoch,time_broker_iso,open,high,low,close,tick_volume,real_volume,bar_spread_points,open_spread_points,open_bid,open_ask,open_tick_time_msc,close_observed_time_msc,flags";
const string HEALTH_HEADER="schema_version,collector_version,run_id,broker_time_epoch,broker_time_iso,terminal_connected,symbol_synchronized,last_tick_age_seconds,last_closed_bar_epoch,rows_written,duplicate_skips,gap_count,write_errors,status";

datetime activeBar=0,lastClosedBar=0;
MqlTick openingTick;
bool eligible=false,stopped=false;
string activeFlags="OK";
long rowsWritten=0,duplicateSkips=0,gapCount=0,writeErrors=0;
ulong lastTickMonotonic=0;
long initialTickAge=-1;

string Iso(const datetime value)
{
   MqlDateTime t;
   TimeToStruct(value,t);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d",t.year,t.mon,t.day,t.hour,t.min,t.sec);
}

string DateKey(const datetime value)
{
   MqlDateTime t;
   TimeToStruct(value,t);
   return StringFormat("%04d%02d%02d",t.year,t.mon,t.day);
}

datetime BrokerNow()
{
   datetime now=TimeTradeServer();
   if(now<=0) now=TimeCurrent();
   return now;
}

// Each append holds an exclusive writer handle, validates the existing header,
// rejects malformed/truncated rows, flushes and closes. No persistent handles.
// For bars, scan the existing day's timestamps to suppress duplicates on restart.
int Append(const string name,const string header,const string row,const datetime bar=0)
{
   ResetLastError();
   int handle=FileOpen(name,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ,0,CP_UTF8);
   if(handle==INVALID_HANDLE) { ++writeErrors; return -1; }
   bool ok=true;
   datetime maximum=0;
   if(FileSize(handle)>0)
   {
      // A complete CRLF terminator is required before appending, including after a crash.
      if(FileSize(handle)<2 || !FileSeek(handle,-2,SEEK_END) || FileReadString(handle)!="") ok=false;
      if(!FileSeek(handle,0,SEEK_SET)) ok=false;
      if(FileReadString(handle)!=header) ok=false;
      while(ok && !FileIsEnding(handle))
      {
         string line=FileReadString(handle);
         if(line=="") { ok=false; break; }
         string fields[];
         int count=StringSplit(line,',',fields);
         if(count!=(bar>0 ? 19 : 14)) { ok=false; break; }
         if(bar>0)
         {
            datetime prior=(datetime)StringToInteger(fields[4]);
            if(prior<=0 || fields[0]!=SCHEMA_VERSION || fields[2]!=RUN_ID || fields[3]!=_Symbol)
               { ok=false; break; }
            if(prior>maximum) maximum=prior;
         }
      }
   }
   if(!ok || GetLastError()!=0) { FileClose(handle); ++writeErrors; return -1; }
   if(bar>0 && bar<=maximum) { FileClose(handle); ++duplicateSkips; return 0; }
   ResetLastError();
   if(!FileSeek(handle,0,SEEK_END)) ok=false;
   if(ok && FileSize(handle)==0 && FileWriteString(handle,header+"\r\n")==0) ok=false;
   if(ok && FileWriteString(handle,row+"\r\n")==0) ok=false;
   FileFlush(handle);
   if(GetLastError()!=0) ok=false;
   FileClose(handle);
   if(!ok) { ++writeErrors; return -1; }
   return 1;
}

// Status precedence: PLANNED_END (final only), WRITE_ERROR, UNSYNCHRONIZED,
// STALE_TICKS (disconnected or age >=300s), MARKET_IDLE (no tick yet), HEALTHY.
void WriteHealth(const datetime now,const bool isFinal=false)
{
   if(now<=0) return;
   bool connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   bool synchronized=SymbolIsSynchronized(_Symbol);
   long age=initialTickAge;
   if(age>=0) age+=(long)((GetTickCount64()-lastTickMonotonic)/1000);
   string status="HEALTHY";
   if(isFinal) status="PLANNED_END";
   else if(writeErrors>0) status="WRITE_ERROR";
   else if(!synchronized) status="UNSYNCHRONIZED";
   else if(!connected || age>=HEALTH_SECONDS) status="STALE_TICKS";
   else if(age<0) status="MARKET_IDLE";
   string row=StringFormat("%s,%s,%s,%I64d,%s,%d,%d,%I64d,%I64d,%I64d,%I64d,%I64d,%I64d,%s",
      SCHEMA_VERSION,COLLECTOR_VERSION,RUN_ID,(long)now,Iso(now),(int)connected,(int)synchronized,
      age,(long)lastClosedBar,rowsWritten,duplicateSkips,gapCount,writeErrors,status);
   Append(DATA_DIR+"QTForward_health_"+DateKey(now)+".csv",HEALTH_HEADER,row);
}

bool StopAtEnd(const datetime now)
{
   if(stopped) return true;
   if(now<PLANNED_END) return false;
   stopped=true;
   eligible=false;
   EventKillTimer();
   WriteHealth(now,true); // One final attempt; never retry or write an active bar.
   return true;
}

void CompleteObservedBar(const MqlTick &tick)
{
   if(!eligible || activeBar<=0) return;
   MqlRates rates[1];
   // Exact tracked observed bar only: no historical warmup or missing-bar fill.
   if(CopyRates(_Symbol,PERIOD_M1,activeBar,1,rates)!=1 || rates[0].time!=activeBar)
   {
      ++gapCount;
      return;
   }
   lastClosedBar=activeBar;
   string flags=activeFlags;
   if(MathAbs(rates[0].open-openingTick.bid)>_Point/2)
      flags=(flags=="OK" ? "OPEN_MISMATCH" : flags+"|OPEN_MISMATCH");
   string row=StringFormat("%s,%s,%s,%s,%I64d,%s,%s,%s,%s,%s,%I64d,%I64d,%d,%s,%s,%s,%I64d,%I64d,%s",
      SCHEMA_VERSION,COLLECTOR_VERSION,RUN_ID,_Symbol,(long)activeBar,Iso(activeBar),
      DoubleToString(rates[0].open,_Digits),DoubleToString(rates[0].high,_Digits),
      DoubleToString(rates[0].low,_Digits),DoubleToString(rates[0].close,_Digits),
      rates[0].tick_volume,rates[0].real_volume,rates[0].spread,
      DoubleToString((openingTick.ask-openingTick.bid)/_Point,4),
      DoubleToString(openingTick.bid,_Digits),DoubleToString(openingTick.ask,_Digits),
      openingTick.time_msc,tick.time_msc,flags);
   if(Append(DATA_DIR+"QTForward_XAUUSD_M1_"+DateKey(activeBar)+".csv",BAR_HEADER,row,activeBar)==1) ++rowsWritten;
}

int OnInit()
{
   if(_Symbol!="XAUUSD" || _Period!=PERIOD_M1 || _Point<=0) return INIT_PARAMETERS_INCORRECT;
   FolderCreate("QTForward");
   ResetLastError();
   if(!EventSetTimer(HEALTH_SECONDS)) return INIT_FAILED;
   datetime now=BrokerNow();
   if(!StopAtEnd(now)) WriteHealth(now);
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   datetime now=BrokerNow();
   if(!StopAtEnd(now)) WriteHealth(now);
}

void OnTick()
{
   if(StopAtEnd(BrokerNow())) return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.time<=0 || tick.bid<=0 || tick.ask<tick.bid) return;
   if(StopAtEnd(tick.time)) return;
   lastTickMonotonic=GetTickCount64();
   initialTickAge=(long)MathMax(0,(long)(BrokerNow()-tick.time));
   datetime barTime=(datetime)((long)tick.time/60*60);
   if(activeBar==0)
   {
      activeBar=barTime; // First attached bar is partial and is always discarded.
      eligible=false;
      return;
   }
   if(barTime<=activeBar) return;
   long missing=(long)(barTime-activeBar)/60-1;
   if(missing>0) gapCount+=missing;
   CompleteObservedBar(tick);
   activeBar=barTime;
   openingTick=tick;
   activeFlags=(missing>0 ? "GAP_BEFORE_BAR" : "OK");
   // Delayed observed opening quote (>5s into bar), retained for diagnostics.
   if(tick.time_msc-(long)barTime*1000>5000)
      activeFlags=(activeFlags=="OK" ? "TICK_DELAY" : activeFlags+"|TICK_DELAY");
   if(MathAbs((double)(tick.time_msc/1000-(long)tick.time))>1 ||
      MathAbs((double)(BrokerNow()-tick.time))>5)
      activeFlags=(activeFlags=="OK" ? "CLOCK_MISMATCH" : activeFlags+"|CLOCK_MISMATCH");
   eligible=true;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   // No bar or health append on unload; the active bar remains uncommitted.
}
