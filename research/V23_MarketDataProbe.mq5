#property strict
#property version "1.00"
input string InpRunTag="market_probe";
int f=INVALID_HANDLE,g=INVALID_HANDLE;
int q=INVALID_HANDLE;
datetime day=0;
long dailyTicks=0,first=0,last=0;
long minuteTicks[1440],minuteBidChanges[1440];
double previousBid=0;
int OnInit()
{
 if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;
 f=FileOpen(InpRunTag+"_daily.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
 g=FileOpen(InpRunTag+"_gaps.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
 q=FileOpen(InpRunTag+"_minute_issues.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
 if(f==INVALID_HANDLE || g==INVALID_HANDLE || q==INVALID_HANDLE) return INIT_FAILED;
 FileWrite(f,"day","ticks","first_msc","last_msc","m1_bars","m1_tick_volume");
 FileWrite(g,"before_msc","after_msc","gap_seconds");
 FileWrite(q,"minute","quote_ticks","bid_changes","bar_present");
 int s=FileOpen(InpRunTag+"_sessions.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
 FileWrite(s,"weekday","session","from","to");
 for(int d=0;d<7;d++) for(uint n=0;n<10;n++)
 {
  datetime a,b;if(!SymbolInfoSessionTrade(_Symbol,(ENUM_DAY_OF_WEEK)d,n,a,b)) break;
  FileWrite(s,d,n,a,b);
 }
 FileClose(s);return INIT_SUCCEEDED;
}
void SaveDay()
{
 if(dailyTicks==0)return;
 MqlRates r[];int count=CopyRates(_Symbol,PERIOD_M1,day,day+86400-1,r);long volume=0;
 int present[1440];ArrayInitialize(present,0);
 for(int i=0;i<count;i++){volume+=r[i].tick_volume;int n=(int)((r[i].time-day)/60);if(n>=0 && n<1440)present[n]=1;}
 int a=(int)((first/1000-day)/60),b=(int)((last/1000-day)/60);
 for(int n=a;n<=b;n++) if(minuteTicks[n]==0 || present[n]==0)
    FileWrite(q,TimeToString(day+n*60,TIME_DATE|TIME_MINUTES),minuteTicks[n],minuteBidChanges[n],present[n]);
 FileWrite(f,TimeToString(day,TIME_DATE),dailyTicks,first,last,count,volume);
}
void OnTick()
{
 MqlTick t;if(!SymbolInfoTick(_Symbol,t))return;
 datetime d=(datetime)((long)t.time/86400*86400);
 if(day!=d){SaveDay();day=d;dailyTicks=0;first=t.time_msc;last=0;ArrayInitialize(minuteTicks,0);ArrayInitialize(minuteBidChanges,0);previousBid=0;}
 int minute=(int)((t.time-day)/60);minuteTicks[minute]++;
 if(t.bid!=previousBid){minuteBidChanges[minute]++;previousBid=t.bid;}
 if(last>0 && t.time_msc-last>300000)FileWrite(g,last,t.time_msc,(t.time_msc-last)/1000.0);
 last=t.time_msc;dailyTicks++;
}
double OnTester(){SaveDay();FileClose(f);FileClose(g);FileClose(q);f=INVALID_HANDLE;g=INVALID_HANDLE;q=INVALID_HANDLE;return 0;}
void OnDeinit(const int reason){if(f!=INVALID_HANDLE)FileClose(f);if(g!=INVALID_HANDLE)FileClose(g);if(q!=INVALID_HANDLE)FileClose(q);}
