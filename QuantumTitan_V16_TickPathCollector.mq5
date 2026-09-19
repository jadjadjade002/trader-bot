//+------------------------------------------------------------------+
//| QuantumTitan V16 Tick-Path Telemetry Collector                   |
//| Read-only research collector. Never sends or modifies trades.    |
//+------------------------------------------------------------------+
#property strict
#property version "16.31"
#property description "Read-only XAUUSD M1 tick-path telemetry for V16 research."

const string SCHEMA_VERSION="2";
const string COLLECTOR_VERSION="16.32";
const string RUN_ID="V16_TICK_PATH_RESEARCH";
const string DATA_DIR="V16TickResearch\\";
const int HORIZON_BARS=15;
const int MAX_PENDING=32;
const int FAVOR_COUNT=12;
const int ADVERSE_COUNT=10;
const int BE_TRIGGER_COUNT=6;
const int BE_LOCK_COUNT=5;
const int SPREAD_BIN_MAX=2000;
const int FAVOR_LEVELS[12]={15,20,30,50,85,100,130,150,180,200,220,240};
const int ADVERSE_LEVELS[10]={15,20,30,50,85,100,130,180,220,260};
const int BE_TRIGGER_LEVELS[6]={50,75,85,100,130,150};
const int BE_LOCK_LEVELS[5]={0,10,15,20,30};

const string BAR_HEADER="schema_version,collector_version,run_id,symbol,signal_bar_epoch,signal_bar_iso,entry_tick_time_msc,horizon_end_time_msc,broker_utc_offset_seconds,session_label,signal_side,signal_score,linreg_slope_current,linreg_slope_previous,ema_fast,ema_slow,rsi,atr_points,signal_bar_range_points,signal_bar_tick_volume,entry_bid,entry_ask,entry_spread_points,spread_mean_points,spread_max_points,spread_p95_points,buy_mfe_points,buy_mae_points,sell_mfe_points,sell_mae_points,buy_mfe_time_msc,buy_mae_time_msc,sell_mfe_time_msc,sell_mae_time_msc,buy_fav_15_msc,buy_fav_20_msc,buy_fav_30_msc,buy_fav_50_msc,buy_fav_85_msc,buy_fav_100_msc,buy_fav_130_msc,buy_fav_150_msc,buy_fav_180_msc,buy_fav_200_msc,buy_fav_220_msc,buy_fav_240_msc,sell_fav_15_msc,sell_fav_20_msc,sell_fav_30_msc,sell_fav_50_msc,sell_fav_85_msc,sell_fav_100_msc,sell_fav_130_msc,sell_fav_150_msc,sell_fav_180_msc,sell_fav_200_msc,sell_fav_220_msc,sell_fav_240_msc,buy_adv_15_msc,buy_adv_20_msc,buy_adv_30_msc,buy_adv_50_msc,buy_adv_85_msc,buy_adv_100_msc,buy_adv_130_msc,buy_adv_180_msc,buy_adv_220_msc,buy_adv_260_msc,sell_adv_15_msc,sell_adv_20_msc,sell_adv_30_msc,sell_adv_50_msc,sell_adv_85_msc,sell_adv_100_msc,sell_adv_130_msc,sell_adv_180_msc,sell_adv_220_msc,sell_adv_260_msc,buy_be_t50_l0_recross_msc,buy_be_t50_l10_recross_msc,buy_be_t50_l15_recross_msc,buy_be_t50_l20_recross_msc,buy_be_t50_l30_recross_msc,buy_be_t75_l0_recross_msc,buy_be_t75_l10_recross_msc,buy_be_t75_l15_recross_msc,buy_be_t75_l20_recross_msc,buy_be_t75_l30_recross_msc,buy_be_t85_l0_recross_msc,buy_be_t85_l10_recross_msc,buy_be_t85_l15_recross_msc,buy_be_t85_l20_recross_msc,buy_be_t85_l30_recross_msc,buy_be_t100_l0_recross_msc,buy_be_t100_l10_recross_msc,buy_be_t100_l15_recross_msc,buy_be_t100_l20_recross_msc,buy_be_t100_l30_recross_msc,buy_be_t130_l0_recross_msc,buy_be_t130_l10_recross_msc,buy_be_t130_l15_recross_msc,buy_be_t130_l20_recross_msc,buy_be_t130_l30_recross_msc,buy_be_t150_l0_recross_msc,buy_be_t150_l10_recross_msc,buy_be_t150_l15_recross_msc,buy_be_t150_l20_recross_msc,buy_be_t150_l30_recross_msc,sell_be_t50_l0_recross_msc,sell_be_t50_l10_recross_msc,sell_be_t50_l15_recross_msc,sell_be_t50_l20_recross_msc,sell_be_t50_l30_recross_msc,sell_be_t75_l0_recross_msc,sell_be_t75_l10_recross_msc,sell_be_t75_l15_recross_msc,sell_be_t75_l20_recross_msc,sell_be_t75_l30_recross_msc,sell_be_t85_l0_recross_msc,sell_be_t85_l10_recross_msc,sell_be_t85_l15_recross_msc,sell_be_t85_l20_recross_msc,sell_be_t85_l30_recross_msc,sell_be_t100_l0_recross_msc,sell_be_t100_l10_recross_msc,sell_be_t100_l15_recross_msc,sell_be_t100_l20_recross_msc,sell_be_t100_l30_recross_msc,sell_be_t130_l0_recross_msc,sell_be_t130_l10_recross_msc,sell_be_t130_l15_recross_msc,sell_be_t130_l20_recross_msc,sell_be_t130_l30_recross_msc,sell_be_t150_l0_recross_msc,sell_be_t150_l10_recross_msc,sell_be_t150_l15_recross_msc,sell_be_t150_l20_recross_msc,sell_be_t150_l30_recross_msc,observed_tick_count,completed_bar_count,largest_tick_gap_msc,missing_bar_count,disconnect_seen,rollover_seen,label_status,quality_flags";

struct PendingRecord
{
   datetime signalBar;
   long entryMsc;
   long horizonEndMsc;
   int brokerOffset;
   string session;
   string side;
   double score;
   double slopeCurrent;
   double slopePrevious;
   double emaFast;
   double emaSlow;
   double rsi;
   double atrPoints;
   double rangePoints;
   long tickVolume;
   double entryBid;
   double entryAsk;
   double spreadSum;
   double spreadMax;
   long spreadHistogram[2001];
   bool spreadHistogramOverflow;
   double buyMfe;
   double buyMae;
   double sellMfe;
   double sellMae;
   long buyMfeTime;
   long buyMaeTime;
   long sellMfeTime;
   long sellMaeTime;
   long buyFav[12];
   long sellFav[12];
   long buyAdv[10];
   long sellAdv[10];
   bool buyBeArmed[6];
   bool sellBeArmed[6];
   long buyBeRecross[30];
   long sellBeRecross[30];
   long observedTicks;
   int completedBars;
   long largestGapMsc;
   long lastObservedTickMsc;
   int missingBars;
   bool disconnect;
   bool rollover;
};

PendingRecord queue[32];
int queueCount=0;
datetime activeBar=0;
long lastTickMsc=0;
long lastTickCount=0;
long rowsWritten=0;
long writeErrors=0;
long duplicateSkips=0;

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

int BrokerOffsetSeconds()
{
   datetime gmt=TimeGMT();
   datetime srv=BrokerNow();
   if(gmt<=0 || srv<=0) return 0;
   return (int)(srv-gmt);
}

bool IsUsSummer(const datetime utc)
{
   MqlDateTime t;
   TimeToStruct(utc,t);
   if(t.mon<3 || t.mon>11) return false;
   if(t.mon>3 && t.mon<11) return true;
   MqlDateTime first;
   first.year=t.year; first.mon=t.mon; first.day=1; first.hour=0; first.min=0; first.sec=0;
   datetime d=StructToTime(first);
   TimeToStruct(d,first);
   int firstSun=(first.day_of_week==0 ? 1 : 8-first.day_of_week);
   if(t.mon==3) return t.day>firstSun+7 || (t.day==firstSun+7 && t.hour>=2);
   return t.day<firstSun || (t.day==firstSun && t.hour<2);
}

bool IsUkSummer(const datetime utc)
{
   MqlDateTime t;
   TimeToStruct(utc,t);
   if(t.mon<3 || t.mon>10) return false;
   if(t.mon>3 && t.mon<10) return true;
   MqlDateTime last;
   last.year=t.year; last.mon=t.mon; last.day=31; last.hour=0; last.min=0; last.sec=0;
   datetime d=StructToTime(last);
   TimeToStruct(d,last);
   int lastSunday=31-last.day_of_week;
   if(t.mon==3) return t.day>lastSunday || (t.day==lastSunday && t.hour>=1);
   return t.day<lastSunday || (t.day==lastSunday && t.hour<1);
}

string SessionLabel(const datetime serverTime)
{
   int off=BrokerOffsetSeconds();
   datetime utc=serverTime-off;
   MqlDateTime u;
   TimeToStruct(utc,u);
   int sec=u.hour*3600+u.min*60+u.sec;
   bool usSummer=IsUsSummer(utc);
   bool ukSummer=IsUkSummer(utc);
   int londonOpen=ukSummer ? 7*3600 : 8*3600;
   int londonClose=ukSummer ? 15*3600+1800 : 16*3600+1800;
   int nyOpen=usSummer ? 13*3600+1800 : 14*3600+1800;
   int nyClose=usSummer ? 20*3600 : 21*3600;
   string s="ASIA";
   if(sec>=nyOpen && sec<londonClose) s="OVERLAP_LDN_NY";
   else if(sec>=londonClose && sec<nyClose) s="NY";
   else if(sec>=londonOpen && sec<nyOpen) s="LONDON";
   else if(sec>=nyClose) s="ROLLOVER";
   return s;
}

double Ema(const MqlRates &r[],const int n,const int period)
{
   if(n<period) return 0.0;
   double alpha=2.0/(period+1.0);
   double value=r[0].close;
   for(int i=1;i<n;i++) value=alpha*r[i].close+(1.0-alpha)*value;
   return value;
}

double Slope(const MqlRates &r[],const int n,const int start,const int period)
{
   if(start<0 || start+period>n || period<2) return 0.0;
   double sx=0.0,sy=0.0,sxx=0.0,sxy=0.0;
   for(int i=0;i<period;i++)
   {
      double x=(double)i;
      double y=r[start+i].close;
      sx+=x; sy+=y; sxx+=x*x; sxy+=x*y;
   }
   double den=period*sxx-sx*sx;
   if(MathAbs(den)<1e-12) return 0.0;
   return (period*sxy-sx*sy)/den/_Point;
}

double Rsi(const MqlRates &r[],const int n,const int period)
{
   if(n<=period) return 50.0;
   double gain=0.0,loss=0.0;
   for(int i=n-period;i<n;i++)
   {
      double d=r[i].close-r[i-1].close;
      if(d>0) gain+=d; else loss-=d;
   }
   if(loss<=0.0) return 100.0;
   if(gain<=0.0) return 0.0;
   return 100.0-(100.0/(1.0+gain/loss));
}

double Atr(const MqlRates &r[],const int n,const int period)
{
   if(n<=period) return 0.0;
   double total=0.0;
   for(int i=n-period;i<n;i++)
   {
      double a=r[i].high-r[i].low;
      double b=MathAbs(r[i].high-r[i-1].close);
      double c=MathAbs(r[i].low-r[i-1].close);
      total+=MathMax(a,MathMax(b,c));
   }
   return total/period/_Point;
}

string Num(const double value,const int digits=4)
{
   if(value==EMPTY_VALUE) return "";
   return DoubleToString(value,digits);
}

double PointSteps(const double priceDelta)
{
   // XAUUSD quotes are discrete _Point steps. Normalize before threshold tests
   // so binary floating-point cannot miss an exact level touch.
   return (double)MathRound(priceDelta/_Point);
}

string LongOrNull(const long value)
{
   if(value<=0) return "";
   return IntegerToString(value);
}

void Add(string &row,const string value)
{
   if(row!="") row+=",";
   row+=value;
}

double SpreadP95(PendingRecord &p)
{
   if(p.observedTicks<=0) return 0.0;
   long target=(long)MathCeil(0.95*(double)p.observedTicks);
   long cumulative=0;
   for(int i=0;i<=SPREAD_BIN_MAX;i++)
   {
      cumulative+=p.spreadHistogram[i];
      if(cumulative>=target) return (double)i;
   }
   return (double)SPREAD_BIN_MAX;
}

bool AppendRow(const string name,const string row,const datetime signalBar,const string side)
{
   ResetLastError();
   int h=FileOpen(name,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ,0,CP_UTF8);
   if(h==INVALID_HANDLE) { writeErrors++; return false; }
   bool ok=true;
   if(FileSize(h)==0)
   {
      if(FileWriteString(h,BAR_HEADER+"\r\n")==0) ok=false;
   }
   else
   {
      if(!FileSeek(h,0,SEEK_SET)) ok=false;
      if(ok && FileReadString(h)!=BAR_HEADER) ok=false;
      while(ok && !FileIsEnding(h))
      {
         string line=FileReadString(h);
         if(line=="") continue;
         string fields[];
         int count=StringSplit(line,',',fields);
         if(count<11) { ok=false; break; }
         if((datetime)StringToInteger(fields[4])==signalBar && fields[10]==side)
         {
            FileClose(h); duplicateSkips++; return false;
         }
      }
      if(ok && !FileSeek(h,0,SEEK_END)) ok=false;
   }
   if(ok && FileWriteString(h,row+"\r\n")==0) ok=false;
   FileFlush(h);
   if(GetLastError()!=0) ok=false;
   FileClose(h);
   if(!ok) writeErrors++;
   return ok;
}

void AddTimestampArray(string &row,const long &values[],const int count)
{
   for(int i=0;i<count;i++) Add(row,LongOrNull(values[i]));
}

void UpdatePath(PendingRecord &p,const MqlTick &tick)
{
   double spread=PointSteps(tick.ask-tick.bid);
   long gap=(p.lastObservedTickMsc>0 ? tick.time_msc-p.lastObservedTickMsc : 0);
   p.observedTicks++;
   p.spreadSum+=spread;
   if(spread>p.spreadMax) p.spreadMax=spread;
   int spreadBin=(int)spread;
   if(spreadBin<0) spreadBin=0;
   if(spreadBin>SPREAD_BIN_MAX) { spreadBin=SPREAD_BIN_MAX; p.spreadHistogramOverflow=true; }
   p.spreadHistogram[spreadBin]++;
   if(gap>p.largestGapMsc) p.largestGapMsc=gap;
   p.lastObservedTickMsc=tick.time_msc;
   if(SessionLabel(tick.time)=="ROLLOVER") p.rollover=true;
   // Executable PnL: buys enter at ask and exit at bid; sells enter at bid and exit at ask.
   double buyMove=PointSteps(tick.bid-p.entryAsk);
   double sellMove=PointSteps(p.entryBid-tick.ask);
   double buyAdvMove=PointSteps(p.entryAsk-tick.bid);
   double sellAdvMove=PointSteps(tick.ask-p.entryBid);
   if(buyMove>p.buyMfe) { p.buyMfe=buyMove; p.buyMfeTime=tick.time_msc; }
   if(buyAdvMove>p.buyMae) { p.buyMae=buyAdvMove; p.buyMaeTime=tick.time_msc; }
   if(sellMove>p.sellMfe) { p.sellMfe=sellMove; p.sellMfeTime=tick.time_msc; }
   if(sellAdvMove>p.sellMae) { p.sellMae=sellAdvMove; p.sellMaeTime=tick.time_msc; }
   for(int i=0;i<FAVOR_COUNT;i++)
   {
      if(p.buyFav[i]<=0 && buyMove>=FAVOR_LEVELS[i]) p.buyFav[i]=tick.time_msc;
      if(p.sellFav[i]<=0 && sellMove>=FAVOR_LEVELS[i]) p.sellFav[i]=tick.time_msc;
   }
   for(int i=0;i<ADVERSE_COUNT;i++)
   {
      if(p.buyAdv[i]<=0 && buyAdvMove>=ADVERSE_LEVELS[i]) p.buyAdv[i]=tick.time_msc;
      if(p.sellAdv[i]<=0 && sellAdvMove>=ADVERSE_LEVELS[i]) p.sellAdv[i]=tick.time_msc;
   }
   for(int trigger=0;trigger<BE_TRIGGER_COUNT;trigger++)
   {
      if(buyMove>=BE_TRIGGER_LEVELS[trigger]) p.buyBeArmed[trigger]=true;
      if(sellMove>=BE_TRIGGER_LEVELS[trigger]) p.sellBeArmed[trigger]=true;
      for(int lock=0;lock<BE_LOCK_COUNT;lock++)
      {
         int index=trigger*BE_LOCK_COUNT+lock;
         if(p.buyBeArmed[trigger] && p.buyBeRecross[index]<=0 && buyMove<=BE_LOCK_LEVELS[lock])
            p.buyBeRecross[index]=tick.time_msc;
         if(p.sellBeArmed[trigger] && p.sellBeRecross[index]<=0 && sellMove<=BE_LOCK_LEVELS[lock])
            p.sellBeRecross[index]=tick.time_msc;
      }
   }
}

string BuildRow(PendingRecord &p,const string status,const string flags)
{
   string row="";
   Add(row,SCHEMA_VERSION); Add(row,COLLECTOR_VERSION); Add(row,RUN_ID); Add(row,_Symbol);
   Add(row,IntegerToString((long)p.signalBar)); Add(row,Iso(p.signalBar));
   Add(row,LongOrNull(p.entryMsc)); Add(row,LongOrNull(p.horizonEndMsc));
   Add(row,IntegerToString(p.brokerOffset)); Add(row,p.session); Add(row,p.side);
   Add(row,Num(p.score)); Add(row,Num(p.slopeCurrent)); Add(row,Num(p.slopePrevious));
   Add(row,Num(p.emaFast,_Digits)); Add(row,Num(p.emaSlow,_Digits)); Add(row,Num(p.rsi,3));
   Add(row,Num(p.atrPoints)); Add(row,Num(p.rangePoints)); Add(row,IntegerToString(p.tickVolume));
   Add(row,Num(p.entryBid,_Digits)); Add(row,Num(p.entryAsk,_Digits));
   Add(row,Num((p.entryAsk-p.entryBid)/_Point));
   Add(row,Num(p.observedTicks>0 ? p.spreadSum/p.observedTicks : 0.0)); Add(row,Num(p.spreadMax));
   Add(row,Num(SpreadP95(p))); Add(row,Num(p.buyMfe)); Add(row,Num(p.buyMae)); Add(row,Num(p.sellMfe)); Add(row,Num(p.sellMae));
   Add(row,LongOrNull(p.buyMfeTime)); Add(row,LongOrNull(p.buyMaeTime)); Add(row,LongOrNull(p.sellMfeTime)); Add(row,LongOrNull(p.sellMaeTime));
   AddTimestampArray(row,p.buyFav,FAVOR_COUNT); AddTimestampArray(row,p.sellFav,FAVOR_COUNT);
   AddTimestampArray(row,p.buyAdv,ADVERSE_COUNT); AddTimestampArray(row,p.sellAdv,ADVERSE_COUNT);
   AddTimestampArray(row,p.buyBeRecross,BE_TRIGGER_COUNT*BE_LOCK_COUNT);
   AddTimestampArray(row,p.sellBeRecross,BE_TRIGGER_COUNT*BE_LOCK_COUNT);
   Add(row,IntegerToString(p.observedTicks)); Add(row,IntegerToString(p.completedBars)); Add(row,LongOrNull(p.largestGapMsc));
   Add(row,IntegerToString(p.missingBars)); Add(row,p.disconnect ? "1" : "0"); Add(row,p.rollover ? "1" : "0");
   Add(row,status); Add(row,flags);
   return row;
}

void Flush(const int index,const string status,const string flags)
{
   PendingRecord p=queue[index];
   string name=DATA_DIR+"V16TickTelemetry_XAUUSD_M1_"+DateKey(p.signalBar)+".csv";
   if(AppendRow(name,BuildRow(p,status,flags),p.signalBar,p.side)) rowsWritten++;
}

void RemoveFront()
{
   for(int i=0;i<queueCount-1;i++) queue[i]=queue[i+1];
   if(queueCount>0) queueCount--;
}

string RecordStatus(PendingRecord &p)
{
   if(p.disconnect) return "INVALID_DISCONNECT";
   if(p.missingBars>0) return "INVALID_GAP";
   if(p.rollover) return "INVALID_ROLLOVER";
   return "COMPLETE";
}

string RecordFlags(PendingRecord &p)
{
   string flags="OK";
   if(p.missingBars>0) flags="MISSING_BAR";
   if(p.disconnect) flags=(flags=="OK" ? "DISCONNECT" : flags+"|DISCONNECT");
   if(p.rollover) flags=(flags=="OK" ? "ROLLOVER" : flags+"|ROLLOVER");
   if(p.spreadHistogramOverflow) flags=(flags=="OK" ? "SPREAD_HIST_CAP" : flags+"|SPREAD_HIST_CAP");
   return flags;
}

void AdvanceCompletedBar(const long horizonEndMsc)
{
   for(int i=0;i<queueCount;i++) queue[i].completedBars++;
   while(queueCount>0 && queue[0].completedBars>=HORIZON_BARS)
   {
      queue[0].horizonEndMsc=horizonEndMsc;
      Flush(0,RecordStatus(queue[0]),RecordFlags(queue[0]));
      RemoveFront();
   }
}

void ProcessClosedBar(const datetime closedBar,const MqlTick &entryTick)
{
   MqlRates r[];
   ArraySetAsSeries(r,false);
   int copied=CopyRates(_Symbol,PERIOD_M1,closedBar-40*60,closedBar,r);
   if(copied<31 || queueCount>=MAX_PENDING) return;
   MqlRates signal=r[copied-1];
   double fast=Ema(r,copied,9),slow=Ema(r,copied,20);
   double slopeNow=Slope(r,copied,copied-10,10);
   double slopePrev=Slope(r,copied,copied-11,10);
   string side=(signal.close>=fast ? "BUY" : "SELL");
   double score=MathAbs(fast-slow)/_Point;
   PendingRecord p;
   p.signalBar=closedBar; p.entryMsc=entryTick.time_msc; p.horizonEndMsc=0;
   p.brokerOffset=BrokerOffsetSeconds(); p.session=SessionLabel(closedBar); p.side=side; p.score=score;
   p.slopeCurrent=slopeNow; p.slopePrevious=slopePrev; p.emaFast=fast; p.emaSlow=slow; p.rsi=Rsi(r,copied,14);
   p.atrPoints=Atr(r,copied,14); p.rangePoints=(signal.high-signal.low)/_Point; p.tickVolume=signal.tick_volume;
   p.entryBid=entryTick.bid; p.entryAsk=entryTick.ask; p.spreadSum=0; p.spreadMax=0; p.spreadHistogramOverflow=false;
   p.buyMfe=0; p.buyMae=0; p.sellMfe=0; p.sellMae=0; p.buyMfeTime=0; p.buyMaeTime=0; p.sellMfeTime=0; p.sellMaeTime=0;
   p.observedTicks=0; p.completedBars=0; p.largestGapMsc=0; p.lastObservedTickMsc=0; p.missingBars=0; p.disconnect=false; p.rollover=(StringFind(p.session,"ROLLOVER")>=0);
   for(int i=0;i<=SPREAD_BIN_MAX;i++) p.spreadHistogram[i]=0;
   for(int i=0;i<FAVOR_COUNT;i++) { p.buyFav[i]=0; p.sellFav[i]=0; }
   for(int i=0;i<ADVERSE_COUNT;i++) { p.buyAdv[i]=0; p.sellAdv[i]=0; }
   for(int i=0;i<BE_TRIGGER_COUNT;i++) { p.buyBeArmed[i]=false; p.sellBeArmed[i]=false; }
   for(int i=0;i<BE_TRIGGER_COUNT*BE_LOCK_COUNT;i++) { p.buyBeRecross[i]=0; p.sellBeRecross[i]=0; }
   queue[queueCount++]=p;
}

int OnInit()
{
   if(_Symbol!="XAUUSD" || _Period!=PERIOD_M1 || _Point<=0) return INIT_FAILED;
   FolderCreate("V16TickResearch");
   EventSetTimer(1);
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
      for(int i=0;i<queueCount;i++) queue[i].disconnect=true;
}

void OnTick()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.time<=0 || tick.time_msc<=0 || tick.bid<=0 || tick.ask<tick.bid) return;
   datetime bar=(datetime)((long)tick.time/60*60);
   if(activeBar==0) { activeBar=bar; lastTickMsc=tick.time_msc; lastTickCount=tick.time_msc; return; }
   if(bar>activeBar)
   {
      long missing=((long)(bar-activeBar)/60)-1;
      if(missing>0) for(int i=0;i<queueCount;i++) queue[i].missingBars+=(int)missing;
      AdvanceCompletedBar(lastTickMsc);
      ProcessClosedBar(activeBar,tick);
      activeBar=bar;
   }
   for(int i=0;i<queueCount;i++) UpdatePath(queue[i],tick);
   lastTickMsc=tick.time_msc; lastTickCount=tick.time_msc;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   // INCOMPLETE_HORIZON records intentionally remain memory-only and are discarded.
}
//+------------------------------------------------------------------+
