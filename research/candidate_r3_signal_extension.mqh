// Inlined by build_candidate_r3.py. Tester-only. R3 signal rules only.
input string InpRunTag="r3bench";
input int InpExperimentMode=0; // 0 exact V24; 1 blowoff fade; 2 internal range; 3 efficient flag
input int InpEntryStrength=0; // preset index 0/1; family-specific frozen axis
int frameFile=INVALID_HANDLE;
int frameMonthFile=INVALID_HANDLE;
int diagnosticFile=INVALID_HANDLE;
string candidateReason="not_evaluated";
int candidateTrend=0,candidateSide=0;
double diagnosticBody=0,diagnosticCloseLocation=0,diagnosticLevel=0;

// R3 has no exit or risk optimizer. V24 SL=1.5 ATR, TP=2R, hold=60, BE off.
bool ValidateR3Inputs()
{
   if(!MQLInfoInteger(MQL_TESTER)) return false;
   if(InpExperimentMode<0 || InpExperimentMode>3 || InpEntryStrength<0 || InpEntryStrength>1
      || (InpExperimentMode==0 && InpEntryStrength!=0)
      || InpFadeBreakouts || InpStopLossATRMul!=1.5 || InpTakeProfitRRMul!=2.0
      || InpATRPeriod!=14 || InpMaxHoldBars!=60 || InpEnableHardSL!=true
      || InpEnableMarginGuard!=true || InpEnableCircuitBreaker!=true
      || InpMaxConsecutiveLosses!=4 || InpCooldownMinutes!=90 || InpMinSLPoints!=150
      || InpLotSize!=0.01 || InpEnableSessionGuard!=false || InpEnableSpreadGuard!=false
      || InpTargetAccount!=0) return false;
   return true;
}

bool BenchInitR3()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION)) return true;
   rawFile=FileOpen(InpRunTag+"_raw.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   diagnosticFile=FileOpen(InpRunTag+"_signals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(rawFile==INVALID_HANDLE || diagnosticFile==INVALID_HANDLE) return false;
   FileWrite(rawFile,"bar","tick_msc","original","closeback","dc_low","dc_high","atr","break_close","retest_open","retest_close","retest_high","retest_low","bid","ask","held_before","cooldown_before","gate","order_attempt","retcode","order_ticket","deal_ticket");
   FileWrite(diagnosticFile,"bar","tick_msc","mode","entry_strength","signal","trend","reason","body_atr","close_location","entry_level","execution_gate","held_before","order_attempt");
   return true;
}

bool CopyR3Rates(ENUM_TIMEFRAMES tf,int count,MqlRates &r[])
{
   if(count<1) return false;
   ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,tf,1,count,r)!=count) return false;
   datetime latestClosed=iTime(_Symbol,tf,1);
   if(latestClosed<=0 || r[0].time!=latestClosed) return false;
   int seconds=(tf==PERIOD_M5 ? 300 : 60);
   for(int i=0;i<count-1;i++) if(r[i].time-r[i+1].time!=seconds) return false;
   for(int i=0;i<count;i++)
   {
      if(!MathIsValidNumber(r[i].open) || !MathIsValidNumber(r[i].high)
         || !MathIsValidNumber(r[i].low) || !MathIsValidNumber(r[i].close)
         || r[i].low<=0 || r[i].high<r[i].low || r[i].high<MathMax(r[i].open,r[i].close)
         || r[i].low>MathMin(r[i].open,r[i].close) || r[i].tick_volume<=0) return false;
   }
   return true;
}

double R3CloseLocation(const MqlRates &r,int direction)
{
   double range=r.high-r.low;
   if(range<=0) return -1;
   return direction>0 ? (r.close-r.low)/range : (r.high-r.close)/range;
}

bool R3ValidSignalCandle(const MqlRates &r,double atr)
{
   double range=r.high-r.low;
   return MathIsValidNumber(atr) && atr>0 && range>0 && range<=2.0*atr;
}

// Context-injected closed M5 trend direction, shared by A and C fixtures.
int R3Trend(const double &ema20[],double ema50,double m5atr)
{
   if(!MathIsValidNumber(m5atr) || m5atr<=0 || !MathIsValidNumber(ema50)) return 0;
   for(int i=0;i<6;i++) if(!MathIsValidNumber(ema20[i])) return 0;
   if(ema20[0]>ema50 && ema20[0]>ema20[5] && ema20[0]-ema50>=0.10*m5atr) return 1;
   if(ema20[0]<ema50 && ema20[0]<ema20[5] && ema50-ema20[0]>=0.10*m5atr) return -1;
   return 0;
}

// Pure quote economics gate, separated from SymbolInfoTick for fixtures.
bool R3QuoteCost(double bid,double ask,double signalClose,double atr)
{
   if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) || !MathIsValidNumber(signalClose)
      || !MathIsValidNumber(atr) || bid<=0 || ask<bid || atr<=0) return false;
   return ask-bid<=0.10*atr && MathAbs((ask+bid)/2.0-signalClose)<=0.50*atr;
}
int ClosedTrendDirection()
{
   double fast,slow,past,a,e9,e20;
   if(!ReadClosed(trendFast,1,fast) || !ReadClosed(trendSlow,1,slow)
      || !ReadClosed(trendFast,6,past) || !ReadClosed(trendATR,1,a)
      || !ReadClosed(entryFast,1,e9) || !ReadClosed(entrySlow,1,e20) || a<=0) return 0;
   if(fast>slow && fast>past && fast-slow>=0.1*a && e9>e20) return 1;
   if(fast<slow && fast<past && slow-fast>=0.1*a && e9<e20) return -1;
   return 0;
}

// Pure, closed-context predicate. Arrays are series: [0]=shift1, [1]=shift2.
int R3Blowoff(int preset,const MqlRates &m1[],const double &atr[],
              const double &ema20[],double ema50,double m5atr,const double &ema9[])
{
   if(preset<0 || preset>1 || !R3ValidSignalCandle(m1[0],atr[0])
      || !MathIsValidNumber(m5atr) || m5atr<=0) return 0;
   int d=R3Trend(ema20,ema50,m5atr);
   if(d==0) return 0;
   double slopeNow=d*(ema20[0]-ema20[1]);
   double slopePrior=d*(ema20[1]-ema20[5])/4.0;
   if(slopePrior<=0 || slopeNow<=0 || slopeNow>0.50*slopePrior) return 0;
   double x=(preset==0 ? 1.50 : 2.00);
   if(!MathIsValidNumber(atr[1]) || atr[1]<=0 || d*(m1[1].close-m1[8].close)<x*atr[1]) return 0;
   double priorExtreme=d>0 ? m1[2].high : m1[2].low;
   for(int i=3;i<=11;i++) priorExtreme=d>0 ? MathMax(priorExtreme,m1[i].high) : MathMin(priorExtreme,m1[i].low);
   if(d>0)
   {
      double e9prior=ema9[1];
      if(m1[1].high<=priorExtreme || m1[0].high<m1[1].high+0.05*atr[0]
         || m1[0].close>=m1[1].high || m1[0].close>=m1[0].open
         || m1[1].close<e9prior || m1[0].close>=ema9[0]
         || MathAbs(m1[0].close-ema9[0])>0.50*atr[0]
         || R3CloseLocation(m1[0],-1)<0.70) return 0;
      return -1;
   }
   double e9prior=ema9[1];
   if(m1[1].low>=priorExtreme || m1[0].low>m1[1].low-0.05*atr[0]
      || m1[0].close<=m1[1].low || m1[0].close<=m1[0].open
      || m1[1].close>e9prior || m1[0].close<=ema9[0]
      || MathAbs(m1[0].close-ema9[0])>0.50*atr[0]
      || R3CloseLocation(m1[0],1)<0.70) return 0;
   return 1;
}

// Pure internal-band rejection. Boundary sweep is explicitly disallowed.
int R3Range(int preset,const MqlRates &m1[],const double &atr[],
            const double &ema20[],double ema50,double m5atr)
{
   if(preset<0 || preset>1 || !R3ValidSignalCandle(m1[0],atr[0])
      || !MathIsValidNumber(m5atr) || m5atr<=0) return 0;
   if(MathAbs(ema20[0]-ema20[5])>0.10*m5atr || MathAbs(ema20[0]-ema50)>0.20*m5atr) return 0;
   double hi=m1[1].high,lo=m1[1].low;
   for(int i=2;i<=20;i++){hi=MathMax(hi,m1[i].high);lo=MathMin(lo,m1[i].low);}
   double width=hi-lo;
   if(width<2.0*atr[0] || width>6.0*atr[0] || width<=0) return 0;
   double range=m1[0].high-m1[0].low;
   if(range<=0) return 0;
   double pos=(m1[0].close-lo)/width;
   double q=(preset==0 ? 0.80 : 0.85);
   double upperWick=(m1[0].high-MathMax(m1[0].open,m1[0].close))/range;
   double lowerWick=(MathMin(m1[0].open,m1[0].close)-m1[0].low)/range;
   if(pos>=q && m1[0].high<hi && m1[0].close<m1[0].open
      && upperWick>=0.25 && R3CloseLocation(m1[0],-1)>=0.60) return -1;
   if(pos<=1.0-q && m1[0].low>lo && m1[0].close>m1[0].open
      && lowerWick>=0.25 && R3CloseLocation(m1[0],1)>=0.60) return 1;
   return 0;
}

// Pure M5 efficiency + three-bar M1 flag predicate.
int R3EfficientFlag(int preset,const MqlRates &m1[],const MqlRates &m5[],const double &atr[],
                    const double &ema20[],double ema50,double m5atr,const double &ema9[])
{
   if(preset<0 || preset>1 || !R3ValidSignalCandle(m1[0],atr[0])
      || !MathIsValidNumber(m5atr) || m5atr<=0 || !MathIsValidNumber(atr[4]) || atr[4]<=0) return 0;
   double path=0;
   for(int i=0;i<12;i++) path+=MathAbs(m5[i].close-m5[i+1].close);
   if(path<=0) return 0;
   double er=MathAbs(m5[0].close-m5[12].close)/path;
   double e=(preset==0 ? 0.60 : 0.70);
   int d=R3Trend(ema20,ema50,m5atr);
   if(d==0 || er<e || d*(m5[0].close-m5[12].close)<m5atr) return 0;
   double impulse=d*(m1[4].close-m1[7].close);
   if(impulse<atr[4]) return 0;
   if(d*(m1[3].close-m1[3].open)>=0 || d*(m1[2].close-m1[2].open)>=0
      || d*(m1[1].close-m1[1].open)>0) return 0;
   double pullback=d*(m1[4].close-m1[1].close);
   if(pullback<0.15*impulse || pullback>0.60*impulse) return 0;
   double pauseExtreme=d>0 ? m1[1].high : m1[1].low;
   for(int i=2;i<=3;i++) pauseExtreme=d>0 ? MathMax(pauseExtreme,m1[i].high) : MathMin(pauseExtreme,m1[i].low);
   if(d>0 && (m1[0].close<pauseExtreme+0.05*atr[0] || m1[0].close<=ema9[0])) return 0;
   if(d<0 && (m1[0].close>pauseExtreme-0.05*atr[0] || m1[0].close>=ema9[0])) return 0;
   if(R3CloseLocation(m1[0],d)<0.70) return 0;
   return d;
}

bool R3CostGate(const MqlRates &s1,double atr)
{
   MqlTick q;
   if(!SymbolInfoTick(_Symbol,q) || !MathIsValidNumber(q.ask) || !MathIsValidNumber(q.bid)
      || q.bid<=0 || q.ask<q.bid) return false;
   return R3QuoteCost(q.bid,q.ask,s1.close,atr);
}

int CandidateR3Signal(double atr)
{
   candidateTrend=0;candidateSide=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
   if(InpExperimentMode==0){candidateReason="v24_exact_signal";candidateSide=ProposedSignal(atr);return candidateSide;}
   candidateReason="invalid_atr";
   if(!MathIsValidNumber(atr) || atr<=0) return 0;
   MqlRates m1[],m5[];
   candidateReason="closed_history_unavailable";
   if(!CopyR3Rates(PERIOD_M1,23,m1) || !CopyR3Rates(PERIOD_M5,13,m5)) return 0;
   double atrM1[],ema20[],ema50[],m5atr[],ema9[];
   ArraySetAsSeries(atrM1,true);ArraySetAsSeries(ema20,true);ArraySetAsSeries(ema50,true);
   ArraySetAsSeries(m5atr,true);ArraySetAsSeries(ema9,true);
   if(CopyBuffer(atrHandle,0,1,23,atrM1)!=23 || CopyBuffer(trendFast,0,1,6,ema20)!=6
      || CopyBuffer(trendSlow,0,1,1,ema50)!=1 || CopyBuffer(trendATR,0,1,1,m5atr)!=1
      || CopyBuffer(entryFast,0,1,2,ema9)!=2) return 0;
   for(int i=0;i<23;i++) if(!MathIsValidNumber(atrM1[i]) || atrM1[i]<=0) return 0;
   for(int i=0;i<6;i++) if(!MathIsValidNumber(ema20[i])) return 0;
   if(!MathIsValidNumber(ema50[0]) || !MathIsValidNumber(m5atr[0]) || m5atr[0]<=0
      || !MathIsValidNumber(ema9[0]) || !MathIsValidNumber(ema9[1])) return 0;
   candidateReason="cost_or_chase";
   if(!R3CostGate(m1[0],atrM1[0])) return 0;
   candidateReason="entry_pattern_absent";
   if(InpExperimentMode==1) candidateSide=R3Blowoff(InpEntryStrength,m1,atrM1,ema20,ema50[0],m5atr[0],ema9);
   else if(InpExperimentMode==2) candidateSide=R3Range(InpEntryStrength,m1,atrM1,ema20,ema50[0],m5atr[0]);
   else if(InpExperimentMode==3) candidateSide=R3EfficientFlag(InpEntryStrength,m1,m5,atrM1,ema20,ema50[0],m5atr[0],ema9);
   if(candidateSide!=0){candidateReason="r3_candidate_signal";candidateTrend=candidateSide;}
   return candidateSide;
}

void ExportCoverageR3()
{
   int f=FileOpen(InpRunTag+"_coverage.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE)return;
   FileWrite(f,"pass","month","ticks","first_tick_msc","last_tick_msc");
   for(int k=0;k<monthN;k++)FileWrite(f,0,monthIds[k],monthTicks[k],monthFirst[k],monthLast[k]);
   FileClose(f);
}

double ExportOptimizationFrame()
{
   double pnl[];ulong ids[];
   if(!HistorySelect(0,TimeCurrent()))return -DBL_MAX;
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong t=HistoryDealGetTicket(i);
      ENUM_DEAL_TYPE type=(ENUM_DEAL_TYPE)HistoryDealGetInteger(t,DEAL_TYPE);
      if((type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL)
         || HistoryDealGetInteger(t,DEAL_MAGIC)!=InpMagicNumber
         || HistoryDealGetString(t,DEAL_SYMBOL)!=_Symbol)continue;
      ulong id=(ulong)HistoryDealGetInteger(t,DEAL_POSITION_ID);int k=-1;
      for(int j=ArraySize(ids)-1;j>=0;j--)if(ids[j]==id){k=j;break;}
      if(k<0){k=ArraySize(ids);ArrayResize(ids,k+1);ArrayResize(pnl,k+1);ids[k]=id;pnl[k]=0;}
      pnl[k]+=HistoryDealGetDouble(t,DEAL_PROFIT)+HistoryDealGetDouble(t,DEAL_COMMISSION)
         +HistoryDealGetDouble(t,DEAL_SWAP)+HistoryDealGetDouble(t,DEAL_FEE);
   }
   double net=0,pos=0,loss=0;int wins=0;
   for(int i=0;i<ArraySize(pnl);i++){net+=pnl[i];if(pnl[i]>0){pos+=pnl[i];wins++;}else loss-=pnl[i];}
   double d[19];
   d[0]=InpExperimentMode;d[1]=InpStopLossATRMul;d[2]=InpTakeProfitRRMul;d[3]=0;d[4]=0;
   d[5]=net;d[6]=pos;d[7]=loss;d[8]=ArraySize(pnl);d[9]=wins;
   d[10]=TesterStatistics(STAT_EQUITY_DD);d[11]=TesterStatistics(STAT_EQUITYDD_PERCENT);
   d[12]=TesterStatistics(STAT_PROFIT);d[13]=0;d[14]=0;d[15]=(double)seenTicks;
   d[16]=(double)firstTick;d[17]=(double)lastTick;d[18]=InpEntryStrength;
   if(!FrameAdd("r3_native_grid",InpExperimentMode,net,d))return -DBL_MAX;
   for(int k=0;k<monthN;k++)
   {
      double coverage[4];coverage[0]=monthIds[k];coverage[1]=(double)monthTicks[k];
      coverage[2]=(double)monthFirst[k];coverage[3]=(double)monthLast[k];
      if(!FrameAdd("r3_month_coverage",InpExperimentMode,net,coverage))return -DBL_MAX;
   }
   return net;
}

void DrainOptimizationFrames()
{
   if(frameFile==INVALID_HANDLE)return;
   ulong pass;string name;long id;double value;double d[];
   while(FrameNext(pass,name,id,value,d))
   {
      if(name=="r3_month_coverage" && ArraySize(d)==4)
      {
         if(frameMonthFile!=INVALID_HANDLE)FileWrite(frameMonthFile,pass,d[0],d[1],d[2],d[3]);
         continue;
      }
      if(name!="r3_native_grid" || ArraySize(d)!=19)continue;
      FileWrite(frameFile,pass,d[0],d[1],d[2],d[3],d[4],d[5],d[6],d[7],d[8],d[9],d[10],d[11],d[12],d[13],d[14],d[15],d[16],d[17],d[18]);
   }
   FileFlush(frameFile);
   if(frameMonthFile!=INVALID_HANDLE)FileFlush(frameMonthFile);
}

void OnTick()
{
   MqlTick tick;if(!SymbolInfoTick(_Symbol,tick))return;
   if(firstTick==0)firstTick=tick.time_msc;
   lastTick=tick.time_msc;seenTicks++;
   ObserveEquity();if(monthN>0)monthTicks[monthN-1]++;
   datetime bar=iTime(_Symbol,PERIOD_M1,0);
   bool fresh=bar>0 && bar!=observedBar;
   bool held=false;datetime cd=cooldownUntil;
   if(fresh)
   {
      observedBar=bar;held=HasOpenPosition();candidateReason="not_evaluated_execution_block";
      candidateSide=0;candidateTrend=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
   }
   benchGate="no_new_bar";benchAttempt=false;
   ObservePath();OriginalOnTick();ObservePath();ObserveEquity();
   if(fresh && rawFile!=INVALID_HANDLE)
   {
      if(InpExperimentMode==0)candidateTrend=ClosedTrendDirection();
      MqlRates r[];double a[];ArraySetAsSeries(r,true);
      double atr=0,bc=0,ro=0,rc=0,rh=0,rl=0;
      if(CopyRates(_Symbol,PERIOD_M1,1,2,r)==2)
      {bc=r[1].close;ro=r[0].open;rc=r[0].close;rh=r[0].high;rl=r[0].low;}
      if(CopyBuffer(atrHandle,0,1,1,a)==1)atr=a[0];
      FileWrite(rawFile,TimeToString(bar,TIME_DATE|TIME_SECONDS),tick.time_msc,candidateSide,0,0,0,atr,bc,ro,rc,rh,rl,tick.bid,tick.ask,held,cd,benchGate,benchAttempt,benchAttempt?trade.ResultRetcode():0,benchAttempt?trade.ResultOrder():0,benchAttempt?trade.ResultDeal():0);
      FileWrite(diagnosticFile,TimeToString(bar,TIME_DATE|TIME_SECONDS),tick.time_msc,InpExperimentMode,InpEntryStrength,candidateSide,candidateTrend,candidateReason,diagnosticBody,diagnosticCloseLocation,diagnosticLevel,benchGate,held,benchAttempt);
   }
}

void OnTesterInit()
{
   frameFile=FileOpen(InpRunTag+"_optimization.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   frameMonthFile=FileOpen(InpRunTag+"_coverage.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(frameMonthFile!=INVALID_HANDLE)FileWrite(frameMonthFile,"pass","month","ticks","first_tick_msc","last_tick_msc");
   if(frameFile!=INVALID_HANDLE)FileWrite(frameFile,"pass","mode","sl_atr","tp_r","be_r","be_lock_r","net","gross_net_wins","gross_net_losses","positions","wins","equity_dd","equity_dd_pct","native_net","be_attempts","be_rejected","observed_ticks","first_tick_msc","last_tick_msc","entry_strength");
}
void OnTesterPass(){DrainOptimizationFrames();}
void OnTesterDeinit()
{
   DrainOptimizationFrames();
   if(frameFile!=INVALID_HANDLE){FileClose(frameFile);frameFile=INVALID_HANDLE;}
   if(frameMonthFile!=INVALID_HANDLE){FileClose(frameMonthFile);frameMonthFile=INVALID_HANDLE;}
}
