//+------------------------------------------------------------------+
//|                 QuantumTitan_V16_2_TelemetryCollector.mq5       |
//|    Read-only M1 Telemetry Collector for XAUUSD Alpha Research   |
//|    Strictly Non-Trading - Zero Execution - Server Hard SL Prep  |
//+------------------------------------------------------------------+
#property strict
#property version "16.20"
#property description "V16.2 Read-Only Telemetry Collector for XAUUSD M1 Alpha Research."

const string SCHEMA_VERSION="1";
const string COLLECTOR_VERSION="16.20";
const string RUN_ID="V16_2_ALPHA_RESEARCH";
const int HEALTH_SECONDS=300;
const string DATA_DIR="V162Research\\";

const string BAR_HEADER="schema_version,collector_version,run_id,symbol,time_broker_epoch,time_broker_iso,server_hour,dst_session_label,open,high,low,close,tick_volume,bid,ask,spread_points,ker_10,ker_15,ker_20,ker_30,anchored_vwap_london,anchored_vwap_ny,dist_to_vwap_london,dist_to_vwap_ny,atr,quality_flags,return_after_5_bars,return_after_15_bars,label_status";
const string HEALTH_HEADER="schema_version,collector_version,run_id,broker_time_epoch,broker_time_iso,gmt_time_epoch,gmt_time_iso,offset_seconds,server_utc_offset_hours,terminal_connected,symbol_synchronized,last_tick_age_seconds,last_closed_bar_epoch,rows_written,duplicate_skips,gap_count,write_errors,status";

struct PendingRecord
{
   datetime barTime;
   double openPrice;
   double highPrice;
   double lowPrice;
   double closePrice;
   long tickVolume;
   double bidPrice;
   double askPrice;
   int spreadPoints;
   int serverHour;
   string sessionLabel;
   double ker10;
   double ker15;
   double ker20;
   double ker30;
   double vwapLondon;
   double vwapNy;
   double distVwapLondon;
   double distVwapNy;
   double atrValue;
   string flags;
   double futureCloses[15];
   datetime futureBarTimes[15];
   int futureCount;
   bool hasGap;
};

PendingRecord pendingQueue[32];
int pendingCount=0;

datetime activeBar=0,lastClosedBar=0;
MqlTick openingTick;
bool eligible=false;
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

int GetServerGmtOffsetSeconds()
{
   datetime gmt=TimeGMT();
   if(gmt<=0) return 0;
   datetime srv=BrokerNow();
   return (int)(srv-gmt);
}

bool IsUKSummerDST(const datetime dt)
{
   MqlDateTime t;
   TimeToStruct(dt,t);
   if(t.mon<3 || t.mon>10) return false;
   if(t.mon>3 && t.mon<10) return true;

   MqlDateTime endMon;
   endMon.year=t.year; endMon.mon=t.mon; endMon.day=31;
   endMon.hour=0; endMon.min=0; endMon.sec=0;
   datetime dtEnd=StructToTime(endMon);
   TimeToStruct(dtEnd,endMon);
   int lastSun=31-endMon.day_of_week;

   if(t.mon==3) return (t.day>lastSun || (t.day==lastSun && t.hour>=1));
   if(t.mon==10) return (t.day<lastSun || (t.day==lastSun && t.hour<1));
   return false;
}

bool IsUSSummerDST(const datetime dt)
{
   MqlDateTime t;
   TimeToStruct(dt,t);
   if(t.mon<3 || t.mon>11) return false;
   if(t.mon>3 && t.mon<11) return true;

   if(t.mon==3)
   {
      MqlDateTime m1;
      m1.year=t.year; m1.mon=3; m1.day=1;
      m1.hour=0; m1.min=0; m1.sec=0;
      datetime dtM1=StructToTime(m1);
      TimeToStruct(dtM1,m1);
      int firstSun=(m1.day_of_week==0) ? 1 : (8-m1.day_of_week);
      int secondSun=firstSun+7;
      return (t.day>secondSun || (t.day==secondSun && t.hour>=2));
   }
   if(t.mon==11)
   {
      MqlDateTime n1;
      n1.year=t.year; n1.mon=11; n1.day=1;
      n1.hour=0; n1.min=0; n1.sec=0;
      datetime dtN1=StructToTime(n1);
      TimeToStruct(dtN1,n1);
      int firstSun=(n1.day_of_week==0) ? 1 : (8-n1.day_of_week);
      return (t.day<firstSun || (t.day==firstSun && t.hour<2));
   }
   return false;
}

string GetDstSessionLabel(const datetime dt,int &hourOut)
{
   MqlDateTime t;
   TimeToStruct(dt,t);
   hourOut=t.hour;

   int offsetSec=GetServerGmtOffsetSeconds();
   int offsetHours=(int)MathRound((double)offsetSec/3600.0);
   datetime utcTime=dt-offsetSec;

   MqlDateTime u;
   TimeToStruct(utcTime,u);
   int utcSecOfDay=u.hour*3600+u.min*60+u.sec;

   bool ukSummer=IsUKSummerDST(utcTime);
   int ldnOpenUtcSec=ukSummer ? (7*3600) : (8*3600);
   int ldnCloseUtcSec=ukSummer ? (15*3600+1800) : (16*3600+1800);

   bool usSummer=IsUSSummerDST(utcTime);
   int nyOpenUtcSec=usSummer ? (13*3600+1800) : (14*3600+1800);
   int nyCloseUtcSec=usSummer ? (20*3600) : (21*3600);

   string session="ASIA";
   if(utcSecOfDay<ldnOpenUtcSec) session="ASIA";
   else if(utcSecOfDay>=ldnOpenUtcSec && utcSecOfDay<nyOpenUtcSec) session="LONDON";
   else if(utcSecOfDay>=nyOpenUtcSec && utcSecOfDay<ldnCloseUtcSec) session="OVERLAP_LDN_NY";
   else if(utcSecOfDay>=ldnCloseUtcSec && utcSecOfDay<nyCloseUtcSec) session="NY";
   else session="ROLLOVER";

   string dstPrefix=ukSummer ? "BST" : "GMT";
   string offsetStr=StringFormat("UTC%+d",offsetHours);

   return StringFormat("%s_%s_%s",offsetStr,dstPrefix,session);
}

datetime GetLondonAnchorServerTime(const datetime dt)
{
   int offsetSec=GetServerGmtOffsetSeconds();
   datetime utcTime=dt-offsetSec;
   bool ukSummer=IsUKSummerDST(utcTime);
   int londonOpenUtcHour=ukSummer ? 7 : 8;

   MqlDateTime t;
   TimeToStruct(dt,t);
   t.hour=0; t.min=0; t.sec=0;
   datetime dayStart=StructToTime(t);

   datetime anchor=dayStart+londonOpenUtcHour*3600+offsetSec;
   if(dt<anchor) anchor-=86400;
   return anchor;
}

datetime GetNYAnchorServerTime(const datetime dt)
{
   int offsetSec=GetServerGmtOffsetSeconds();
   datetime utcTime=dt-offsetSec;
   bool usSummer=IsUSSummerDST(utcTime);
   int nyOpenUtcSec=usSummer ? (13*3600+1800) : (14*3600+1800);

   MqlDateTime t;
   TimeToStruct(dt,t);
   t.hour=0; t.min=0; t.sec=0;
   datetime dayStart=StructToTime(t);

   datetime anchor=dayStart+nyOpenUtcSec+offsetSec;
   if(dt<anchor) anchor-=86400;
   return anchor;
}

double CalcKER(const MqlRates &rates[],const int total,const int period)
{
   if(total<=period) return 0.0;
   int endIdx=total-1;
   int startIdx=endIdx-period;
   double change=MathAbs(rates[endIdx].close-rates[startIdx].close);
   double sumPath=0.0;
   for(int i=startIdx+1; i<=endIdx; i++)
   {
      sumPath+=MathAbs(rates[i].close-rates[i-1].close);
   }
   if(sumPath<=0.0) return 0.0;
   return change/sumPath;
}

double CalcATR(const MqlRates &rates[],const int total,const int period=14)
{
   if(total<=period) return 0.0;
   int endIdx=total-1;
   int startIdx=endIdx-period+1;
   double sumTR=0.0;
   for(int i=startIdx; i<=endIdx; i++)
   {
      double tr1=rates[i].high-rates[i].low;
      double tr2=MathAbs(rates[i].high-rates[i-1].close);
      double tr3=MathAbs(rates[i].low-rates[i-1].close);
      double tr=MathMax(tr1,MathMax(tr2,tr3));
      sumTR+=tr;
   }
   return sumTR/(double)period;
}

void CalcSessionAnchoredTVWAP(const datetime dt,const double currentClose,double &vwapLondon,double &vwapNy)
{
   vwapLondon=currentClose;
   vwapNy=currentClose;

   datetime ldnAnchor=GetLondonAnchorServerTime(dt);
   datetime nyAnchor=GetNYAnchorServerTime(dt);

   int barsLdn=(int)((dt-ldnAnchor)/60)+1;
   if(barsLdn>0 && barsLdn<=1440)
   {
      MqlRates rLdn[];
      ArraySetAsSeries(rLdn,false);
      int copied=CopyRates(_Symbol,PERIOD_M1,ldnAnchor,dt,rLdn);
      if(copied>0)
      {
         double sumPV=0.0;
         long sumV=0;
         for(int i=0; i<copied; i++)
         {
            double pTyp=(rLdn[i].high+rLdn[i].low+rLdn[i].close)/3.0;
            sumPV+=pTyp*(double)rLdn[i].tick_volume;
            sumV+=rLdn[i].tick_volume;
         }
         if(sumV>0) vwapLondon=sumPV/(double)sumV;
      }
   }

   int barsNy=(int)((dt-nyAnchor)/60)+1;
   if(barsNy>0 && barsNy<=1440)
   {
      MqlRates rNy[];
      ArraySetAsSeries(rNy,false);
      int copied=CopyRates(_Symbol,PERIOD_M1,nyAnchor,dt,rNy);
      if(copied>0)
      {
         double sumPV=0.0;
         long sumV=0;
         for(int i=0; i<copied; i++)
         {
            double pTyp=(rNy[i].high+rNy[i].low+rNy[i].close)/3.0;
            sumPV+=pTyp*(double)rNy[i].tick_volume;
            sumV+=rNy[i].tick_volume;
         }
         if(sumV>0) vwapNy=sumPV/(double)sumV;
      }
   }
}

int Append(const string name,const string header,const string row,const datetime bar=0)
{
   ResetLastError();
   int handle=FileOpen(name,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ,0,CP_UTF8);
   if(handle==INVALID_HANDLE) { ++writeErrors; return -1; }
   bool ok=true;
   datetime maximum=0;
   if(FileSize(handle)>0)
   {
      if(FileSize(handle)<2 || !FileSeek(handle,-2,SEEK_END) || FileReadString(handle)!="") ok=false;
      if(!FileSeek(handle,0,SEEK_SET)) ok=false;
      if(FileReadString(handle)!=header) ok=false;
      while(ok && !FileIsEnding(handle))
      {
         string line=FileReadString(handle);
         if(line=="") { ok=false; break; }
         string fields[];
         int count=StringSplit(line,',',fields);
         if(count!=(bar>0 ? 29 : 18)) { ok=false; break; }
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

void WriteHealth(const datetime now)
{
   if(now<=0) return;
   bool connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   bool synchronized=SymbolIsSynchronized(_Symbol);
   long age=initialTickAge;
   if(age>=0) age+=(long)((GetTickCount64()-lastTickMonotonic)/1000);

   datetime gmtNow=TimeGMT();
   int offsetSec=GetServerGmtOffsetSeconds();
   int offsetHours=(int)MathRound((double)offsetSec/3600.0);

   string status="HEALTHY";
   if(writeErrors>0) status="WRITE_ERROR";
   else if(!synchronized) status="UNSYNCHRONIZED";
   else if(!connected || age>=HEALTH_SECONDS) status="STALE_TICKS";
   else if(age<0) status="MARKET_IDLE";

   string row=StringFormat("%s,%s,%s,%I64d,%s,%I64d,%s,%d,%d,%d,%d,%I64d,%I64d,%I64d,%I64d,%I64d,%I64d,%s",
      SCHEMA_VERSION,COLLECTOR_VERSION,RUN_ID,
      (long)now,Iso(now),
      (long)gmtNow,Iso(gmtNow),
      offsetSec,offsetHours,
      (int)connected,(int)synchronized,
      age,(long)lastClosedBar,rowsWritten,duplicateSkips,gapCount,writeErrors,status);
   Append(DATA_DIR+"V162Telemetry_health_"+DateKey(now)+".csv",HEALTH_HEADER,row);
}

void FlushPendingRecord(const int idx)
{
   bool gapDetected=pendingQueue[idx].hasGap;

   for(int k=0; k<15; k++)
   {
      datetime expectedBarTime=pendingQueue[idx].barTime+(k+1)*60;
      if(pendingQueue[idx].futureBarTimes[k]!=expectedBarTime)
      {
         gapDetected=true;
         break;
      }
   }

   double ret5=0.0;
   double ret15=0.0;
   string labelStatus="COMPLETE";

   if(gapDetected)
   {
      labelStatus="INVALID_GAP";
      ret5=0.0;
      ret15=0.0;
   }
   else
   {
      ret5=(pendingQueue[idx].futureCloses[4]-pendingQueue[idx].closePrice)/_Point;
      ret15=(pendingQueue[idx].futureCloses[14]-pendingQueue[idx].closePrice)/_Point;
   }

   string row=StringFormat("%s,%s,%s,%s,%I64d,%s,%d,%s,%s,%s,%s,%s,%I64d,%s,%s,%d,%.4f,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f,%.3f,%.3f,%s,%.2f,%.2f,%s",
      SCHEMA_VERSION,COLLECTOR_VERSION,RUN_ID,_Symbol,
      (long)pendingQueue[idx].barTime,Iso(pendingQueue[idx].barTime),
      pendingQueue[idx].serverHour,pendingQueue[idx].sessionLabel,
      DoubleToString(pendingQueue[idx].openPrice,_Digits),
      DoubleToString(pendingQueue[idx].highPrice,_Digits),
      DoubleToString(pendingQueue[idx].lowPrice,_Digits),
      DoubleToString(pendingQueue[idx].closePrice,_Digits),
      pendingQueue[idx].tickVolume,
      DoubleToString(pendingQueue[idx].bidPrice,_Digits),
      DoubleToString(pendingQueue[idx].askPrice,_Digits),
      pendingQueue[idx].spreadPoints,
      pendingQueue[idx].ker10,pendingQueue[idx].ker15,
      pendingQueue[idx].ker20,pendingQueue[idx].ker30,
      pendingQueue[idx].vwapLondon,pendingQueue[idx].vwapNy,
      pendingQueue[idx].distVwapLondon,pendingQueue[idx].distVwapNy,
      pendingQueue[idx].atrValue,
      pendingQueue[idx].flags,
      ret5,ret15,labelStatus);

   string fileName=DATA_DIR+"V162Telemetry_XAUUSD_M1_"+DateKey(pendingQueue[idx].barTime)+".csv";
   if(Append(fileName,BAR_HEADER,row,pendingQueue[idx].barTime)==1)
   {
      ++rowsWritten;
   }
}

void ProcessNewClosedBar(const MqlTick &tick)
{
   if(!eligible || activeBar<=0) return;

   MqlRates currentRates[1];
   if(CopyRates(_Symbol,PERIOD_M1,activeBar,1,currentRates)!=1 || currentRates[0].time!=activeBar)
   {
      ++gapCount;
      return;
   }
   lastClosedBar=activeBar;

   for(int i=0; i<pendingCount; i++)
   {
      if(pendingQueue[i].futureCount<15)
      {
         pendingQueue[i].futureCloses[pendingQueue[i].futureCount]=currentRates[0].close;
         pendingQueue[i].futureBarTimes[pendingQueue[i].futureCount]=activeBar;
         pendingQueue[i].futureCount++;
      }
   }

   while(pendingCount>0 && pendingQueue[0].futureCount>=15)
   {
      FlushPendingRecord(0);
      for(int i=0; i<pendingCount-1; i++)
      {
         pendingQueue[i]=pendingQueue[i+1];
      }
      pendingCount--;
   }

   MqlRates histRates[];
   ArraySetAsSeries(histRates,false);
   int copied=CopyRates(_Symbol,PERIOD_M1,activeBar-35*60,activeBar,histRates);

   double ker10=0.0,ker15=0.0,ker20=0.0,ker30=0.0,atrVal=0.0;
   if(copied>30)
   {
      ker10=CalcKER(histRates,copied,10);
      ker15=CalcKER(histRates,copied,15);
      ker20=CalcKER(histRates,copied,20);
      ker30=CalcKER(histRates,copied,30);
      atrVal=CalcATR(histRates,copied,14);
   }

   int hourVal=0;
   string sessionLbl=GetDstSessionLabel(activeBar,hourVal);

   double vLdn=0.0,vNy=0.0;
   CalcSessionAnchoredTVWAP(activeBar,currentRates[0].close,vLdn,vNy);

   string flags=activeFlags;
   if(MathAbs(currentRates[0].open-openingTick.bid)>_Point/2)
      flags=(flags=="OK" ? "OPEN_MISMATCH" : flags+"|OPEN_MISMATCH");

   int spreadPts=(int)MathRound((openingTick.ask-openingTick.bid)/_Point);

   if(pendingCount<32)
   {
      pendingQueue[pendingCount].barTime=activeBar;
      pendingQueue[pendingCount].openPrice=currentRates[0].open;
      pendingQueue[pendingCount].highPrice=currentRates[0].high;
      pendingQueue[pendingCount].lowPrice=currentRates[0].low;
      pendingQueue[pendingCount].closePrice=currentRates[0].close;
      pendingQueue[pendingCount].tickVolume=currentRates[0].tick_volume;
      pendingQueue[pendingCount].bidPrice=openingTick.bid;
      pendingQueue[pendingCount].askPrice=openingTick.ask;
      pendingQueue[pendingCount].spreadPoints=spreadPts;
      pendingQueue[pendingCount].serverHour=hourVal;
      pendingQueue[pendingCount].sessionLabel=sessionLbl;
      pendingQueue[pendingCount].ker10=ker10;
      pendingQueue[pendingCount].ker15=ker15;
      pendingQueue[pendingCount].ker20=ker20;
      pendingQueue[pendingCount].ker30=ker30;
      pendingQueue[pendingCount].vwapLondon=vLdn;
      pendingQueue[pendingCount].vwapNy=vNy;
      pendingQueue[pendingCount].distVwapLondon=currentRates[0].close-vLdn;
      pendingQueue[pendingCount].distVwapNy=currentRates[0].close-vNy;
      pendingQueue[pendingCount].atrValue=atrVal;
      pendingQueue[pendingCount].flags=flags;
      pendingQueue[pendingCount].futureCount=0;
      pendingQueue[pendingCount].hasGap=(flags=="GAP_BEFORE_BAR" || StringFind(flags,"GAP")>=0);
      pendingCount++;
   }
}

int OnInit()
{
   if(_Symbol!="XAUUSD" || _Period!=PERIOD_M1 || _Point<=0)
   {
      return INIT_FAILED;
   }
   FolderCreate("V162Research");
   ResetLastError();
   if(!EventSetTimer(HEALTH_SECONDS)) return INIT_FAILED;
   datetime now=BrokerNow();
   WriteHealth(now);
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   datetime now=BrokerNow();
   WriteHealth(now);
}

void OnTick()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.time<=0 || tick.bid<=0 || tick.ask<tick.bid) return;
   lastTickMonotonic=GetTickCount64();
   initialTickAge=(long)MathMax(0,(long)(BrokerNow()-tick.time));
   datetime barTime=(datetime)((long)tick.time/60*60);

   if(activeBar==0)
   {
      activeBar=barTime;
      eligible=false;
      return;
   }
   if(barTime<=activeBar) return;

   long missing=(long)(barTime-activeBar)/60-1;
   if(missing>0) gapCount+=missing;

   ProcessNewClosedBar(tick);

   activeBar=barTime;
   openingTick=tick;
   activeFlags=(missing>0 ? "GAP_BEFORE_BAR" : "OK");

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
}
//+------------------------------------------------------------------+
