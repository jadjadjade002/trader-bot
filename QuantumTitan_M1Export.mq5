#property strict
#property version "1.00"
#property description "No-trade XAUUSD M1 completed-bar CSV exporter."

input string InpOutputFile="QuantumTitan_M1Export.csv";
input double InpExpectedPoint=0.01;
input double InpExpectedTickSize=0.01;
input long InpMinimumEpoch=0;
input long InpMaximumEpochExclusive=0;

int exportFile=INVALID_HANDLE;
datetime lastBar=0;
datetime lastExported=0;

bool CanonicalXau(string symbol)
{
   StringToUpper(symbol);
   return StringFind(symbol,"XAUUSD")>=0;
}

bool WriteBar(const MqlRates &bar)
{
   if(bar.time<=0 || bar.time<=lastExported) return true;
   if((InpMinimumEpoch>0 && (long)bar.time<InpMinimumEpoch) ||
      (InpMaximumEpochExclusive>0 && (long)bar.time>=InpMaximumEpochExclusive)) return true;
   MqlDateTime parts;
   TimeToStruct(bar.time,parts);
   string iso=StringFormat("%04d-%02d-%02dT%02d:%02d:%02d",parts.year,parts.mon,parts.day,parts.hour,parts.min,parts.sec);
   if(FileWrite(exportFile,(long)bar.time,iso,
      DoubleToString(bar.open,_Digits),DoubleToString(bar.high,_Digits),
      DoubleToString(bar.low,_Digits),DoubleToString(bar.close,_Digits),
      (long)bar.tick_volume,(int)bar.spread,(long)bar.real_volume)<=0) return false;
   FileFlush(exportFile);
   lastExported=bar.time;
   return true;
}

bool ExportLatestCompleted()
{
   MqlRates bars[1];
   if(CopyRates(_Symbol,PERIOD_M1,1,1,bars)!=1) return false;
   return WriteBar(bars[0]);
}

int OnInit()
{
   if(_Period!=PERIOD_M1 || !CanonicalXau(_Symbol)) return INIT_PARAMETERS_INCORRECT;
   if(InpMinimumEpoch<0 || (InpMaximumEpochExclusive>0 && InpMaximumEpochExclusive<=InpMinimumEpoch)) return INIT_PARAMETERS_INCORRECT;
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(MathAbs(_Point-InpExpectedPoint)>1e-12 || MathAbs(tickSize-InpExpectedTickSize)>1e-12) return INIT_PARAMETERS_INCORRECT;
   if(StringLen(InpOutputFile)<1 || StringFind(InpOutputFile,"\\")>=0 || StringFind(InpOutputFile,"/")>=0) return INIT_PARAMETERS_INCORRECT;
   exportFile=FileOpen(InpOutputFile,FILE_READ|FILE_WRITE|FILE_CSV|FILE_SHARE_READ|FILE_ANSI,',',CP_UTF8);
   if(exportFile==INVALID_HANDLE) return INIT_FAILED;
   if(FileSize(exportFile)==0)
   {
      if(FileWrite(exportFile,"time_broker_epoch","time_broker_iso","open","high","low","close","tick_volume","spread_points","real_volume")<=0) return INIT_FAILED;
      FileFlush(exportFile);
   }
   FileSeek(exportFile,0,SEEK_END);
   lastBar=iTime(_Symbol,PERIOD_M1,0);
   PrintFormat("[M1EXPORT] initialized symbol=%s digits=%d point=%.8f tick_size=%.8f file=%s schema=time_broker_epoch,time_broker_iso,open,high,low,close,tick_volume,spread_points,real_volume",_Symbol,_Digits,_Point,tickSize,InpOutputFile);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   datetime currentBar=iTime(_Symbol,PERIOD_M1,0);
   if(currentBar<=0 || currentBar==lastBar) return;
   if(!ExportLatestCompleted()) PrintFormat("[M1EXPORT] failed to export completed bar before %s",TimeToString(currentBar));
   lastBar=currentBar;
}

void OnDeinit(const int reason)
{
   if(exportFile!=INVALID_HANDLE) { FileFlush(exportFile); FileClose(exportFile); exportFile=INVALID_HANDLE; }
}
