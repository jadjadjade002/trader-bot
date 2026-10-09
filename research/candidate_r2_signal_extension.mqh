// Inlined by build_candidate_r2.py. Tester-only. R2 signal rules only.
input string InpRunTag="r2bench";
input int InpExperimentMode=0; // 0 exact V24; 1..5 R2-A..E
input int InpEntryStrength=0; // one of two predeclared presets per R2 family
int frameFile=INVALID_HANDLE;
int frameMonthFile=INVALID_HANDLE;
int diagnosticFile=INVALID_HANDLE;
string candidateReason="not_evaluated";
int candidateTrend=0,candidateSide=0;
double diagnosticBody=0,diagnosticCloseLocation=0,diagnosticLevel=0;
double r2ArmedLevel=0,r2LastArmLevel=0;
int r2ArmedDirection=0,r2ArmedAge=0,r2LastArmDirection=0;
datetime r2ArmedOnBar=0,r2LastProcessedClosedBar=0;
int r2RetestReadySide=0;
datetime r2RetestReadyBar=0,r2ArmHandledBar=0;

void ResetR2State()
{
   r2ArmedLevel=0;r2LastArmLevel=0;
   r2ArmedDirection=0;r2ArmedAge=0;r2LastArmDirection=0;
   r2ArmedOnBar=0;r2LastProcessedClosedBar=0;
   r2RetestReadySide=0;r2RetestReadyBar=0;r2ArmHandledBar=0;
}

// R2 has no exit or risk optimizer. V24 SL=1.5 ATR, TP=2R, hold=60, BE off.
bool ValidateR2Inputs()
{
   if(!MQLInfoInteger(MQL_TESTER)) return false;
   if(InpExperimentMode<0 || InpExperimentMode>5 || InpEntryStrength<0 || InpEntryStrength>1
      || InpFadeBreakouts || InpStopLossATRMul!=1.5 || InpTakeProfitRRMul!=2.0
      || InpMaxHoldBars!=60 || InpEnableHardSL!=true || InpEnableMarginGuard!=true
      || InpEnableCircuitBreaker!=true || InpMaxConsecutiveLosses!=4 || InpCooldownMinutes!=90
      || InpMinSLPoints!=150 || InpLotSize!=0.01 || InpEnableSessionGuard!=false
      || InpEnableSpreadGuard!=false || InpTargetAccount!=0) return false;
   return true;
}

bool BenchInitR2()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION)) return true;
   rawFile=FileOpen(InpRunTag+"_raw.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   diagnosticFile=FileOpen(InpRunTag+"_signals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(rawFile==INVALID_HANDLE || diagnosticFile==INVALID_HANDLE) return false;
   FileWrite(rawFile,"bar","tick_msc","original","closeback","dc_low","dc_high","atr","break_close","retest_open","retest_close","retest_high","retest_low","bid","ask","held_before","cooldown_before","gate","order_attempt","retcode","order_ticket","deal_ticket");
   FileWrite(diagnosticFile,"bar","tick_msc","mode","entry_strength","signal","trend","reason","body_atr","close_location","entry_level","execution_gate","held_before","order_attempt");
   return true;
}

bool CopyR2Rates(int count,MqlRates &r[])
{
   ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,count,r)!=count) return false;
   datetime latestClosed=iTime(_Symbol,PERIOD_M1,1);
   if(count<1 || latestClosed<=0 || r[0].time!=latestClosed) return false;
   for(int i=0;i<count-1;i++)
      if(r[i].time-r[i+1].time!=60) return false;
   for(int i=0;i<count;i++)
   {
      if(!MathIsValidNumber(r[i].open) || !MathIsValidNumber(r[i].high)
         || !MathIsValidNumber(r[i].low) || !MathIsValidNumber(r[i].close)
         || r[i].low<=0 || r[i].high<r[i].low || r[i].high<MathMax(r[i].open,r[i].close)
         || r[i].low>MathMin(r[i].open,r[i].close) || r[i].tick_volume<=0) return false;
   }
   return true;
}

bool ReadR2Context(int &direction,double &m5atr,double &ema9,double &ema20)
{
   double fast,slow,past;
   if(!ReadClosed(trendFast,1,fast) || !ReadClosed(trendSlow,1,slow)
      || !ReadClosed(trendFast,6,past) || !ReadClosed(trendATR,1,m5atr)
      || !ReadClosed(entryFast,1,ema9) || !ReadClosed(entrySlow,1,ema20)
      || !MathIsValidNumber(m5atr) || m5atr<=0) return false;
   direction=0;
   if(fast>slow && fast>past && fast-slow>=0.1*m5atr) direction=1;
   if(fast<slow && fast<past && slow-fast>=0.1*m5atr) direction=-1;
   return true;
}

bool R2M1Aligned(int direction,double ema9,double ema20)
{
   return direction>0 ? ema9>ema20 : (direction<0 && ema9<ema20);
}
int ClosedTrendDirection()
{
   int direction=0;double m5atr,ema9,ema20;
   if(!ReadR2Context(direction,m5atr,ema9,ema20) || !R2M1Aligned(direction,ema9,ema20)) return 0;
   return direction;
}

bool R2RetestTouch(const MqlRates &r,double level,int direction,double atr)
{
   return direction==1 ? (r.low<=level+0.15*atr && r.low>=level-0.15*atr)
                        : (r.high>=level-0.15*atr && r.high<=level+0.15*atr);
}

int R2RetestRule(const MqlRates &r,double level,int direction,double atr,double ema9)
{
   bool buy=direction==1;
   if(!R2RetestTouch(r,level,direction,atr) || MathAbs(r.close-ema9)>0.75*atr
      || !R2TrendCandle(r,buy,atr,0.0)) return 0;
   double pad=(InpEntryStrength==0 ? 0.0 : 0.05)*atr;
   if(buy && r.close>=level+pad && r.close>ema9) return 1;
   if(!buy && r.close<=level-pad && r.close<ema9) return -1;
   return 0;
}

void R2AdvanceArm(int direction,double ema9,double ema20,double atr,const MqlRates &s1)
{
   if(s1.time<=0 || !MathIsValidNumber(atr) || atr<=0
      || !MathIsValidNumber(ema9) || !MathIsValidNumber(ema20))
   {ResetR2State();return;}
   if(r2LastProcessedClosedBar==s1.time) return;
   r2LastProcessedClosedBar=s1.time;
   if(r2RetestReadyBar!=s1.time){r2RetestReadySide=0;r2RetestReadyBar=0;}
   if(r2ArmedDirection!=0)
   {
      r2ArmedAge++;
      bool invalid=(direction!=r2ArmedDirection || !R2M1Aligned(direction,ema9,ema20))
         || (r2ArmedDirection==1 ? s1.close<r2ArmedLevel-0.15*atr
                                 : s1.close>r2ArmedLevel+0.15*atr);
      if(invalid || r2ArmedAge>3)
      {r2ArmedDirection=0;r2ArmedAge=0;r2ArmedLevel=0;r2ArmedOnBar=0;}
      else if(s1.time>r2ArmedOnBar && R2RetestTouch(s1,r2ArmedLevel,r2ArmedDirection,atr))
      {
         r2RetestReadySide=R2RetestRule(s1,r2ArmedLevel,r2ArmedDirection,atr,ema9);
         r2RetestReadyBar=s1.time;r2ArmHandledBar=s1.time;
         r2ArmedDirection=0;r2ArmedAge=0;r2ArmedLevel=0;r2ArmedOnBar=0;
      }
   }
   if(direction!=r2LastArmDirection)
   {r2LastArmLevel=0;r2LastArmDirection=direction;}
}

void R2AdvanceArmOnFreshBar()
{
   if(InpExperimentMode!=4) return;
   MqlRates r[];double m5atr=0,ema9=0,ema20=0;int direction=0;
   double av[];ArraySetAsSeries(av,true);
   if(!CopyR2Rates(23,r) || CopyBuffer(atrHandle,0,1,1,av)!=1
      || !MathIsValidNumber(av[0]) || av[0]<=0
      || !ReadR2Context(direction,m5atr,ema9,ema20))
   { ResetR2State();return; }
   R2AdvanceArm(direction,ema9,ema20,av[0],r[0]);
}

double R2CloseLocation(const MqlRates &r,bool buy)
{
   double range=r.high-r.low;
   if(range<=0) return -1;
   return buy ? (r.close-r.low)/range : (r.high-r.close)/range;
}

bool R2TrendCandle(const MqlRates &r,bool buy,double atr,double minClose)
{
   double range=r.high-r.low;
   if(range<=0 || range>2.0*atr) return false;
   if(buy ? r.close<=r.open : r.close>=r.open) return false;
   return R2CloseLocation(r,buy)>=minClose;
}

bool R2QuoteCost(double bid,double ask,double signalClose,double atr)
{
   if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) || !MathIsValidNumber(signalClose)
      || !MathIsValidNumber(atr) || atr<=0 || bid<=0 || ask<bid) return false;
   return ask-bid<=0.1*atr && MathAbs((ask+bid)/2.0-signalClose)<=0.5*atr;
}
bool R2CostGate(const MqlRates &s1,double atr)
{
   MqlTick q;
   if(!SymbolInfoTick(_Symbol,q) || !MathIsValidNumber(q.ask) || !MathIsValidNumber(q.bid)
      || q.bid<=0 || q.ask<q.bid) return false;
   return R2QuoteCost(q.bid,q.ask,s1.close,atr);
}

int R2Pullback(double atr,int direction,const MqlRates &s1,double ema9,double ema20)
{
   double b=InpEntryStrength==0 ? 0.0 : 0.10*atr;
   bool buy=direction==1;
   if(!R2TrendCandle(s1,buy,atr,0.0)) return 0;
   if(MathAbs(s1.close-ema9)>0.75*atr) return 0;
   if(buy && s1.low<=ema20 && s1.high>=ema20 && s1.close>=ema20+b) return 1;
   if(!buy && s1.low<=ema20 && s1.high>=ema20 && s1.close<=ema20-b) return -1;
   return 0;
}

int R2Compression(double atr,int direction,const MqlRates &r[],double ema9,const double &a2[])
{
   bool buy=direction==1;
   double hi=MathMax(r[1].high,MathMax(r[2].high,r[3].high));
   double lo=MathMin(r[1].low,MathMin(r[2].low,r[3].low));
   if(ArraySize(a2)!=3) return 0;
   for(int i=0;i<3;i++) if(!MathIsValidNumber(a2[i]) || a2[i]<=0 || r[i+1].high-r[i+1].low>0.8*a2[i]) return 0;
   if(hi-lo>1.5*a2[0] || r[0].high-r[0].low>2.0*atr) return 0;
   double pad=(InpEntryStrength==0 ? 0.0 : 0.05)*atr;
   if(!R2TrendCandle(r[0],buy,atr,0.70) || (buy ? r[0].close<=ema9 : r[0].close>=ema9)) return 0;
   if(buy && r[0].close>hi+pad) return 1;
   if(!buy && r[0].close<lo-pad) return -1;
   return 0;
}

int R2RangeReversal(double atr,const MqlRates &r[],double m5fast,double m5slow,double m5past,double m5atr)
{
   if(!MathIsValidNumber(m5fast) || !MathIsValidNumber(m5slow) || !MathIsValidNumber(m5past)
      || !MathIsValidNumber(m5atr) || m5atr<=0) return 0;
   if(MathAbs(m5fast-m5past)>0.10*m5atr || MathAbs(m5fast-m5slow)>0.20*m5atr) return 0;
   double hi=r[1].high,lo=r[1].low;
   for(int i=2;i<=20;i++){hi=MathMax(hi,r[i].high);lo=MathMin(lo,r[i].low);}
   double width=hi-lo;
   if(width<2.0*atr || width>6.0*atr) return 0;
   double minSweep=(InpEntryStrength==0 ? 0.05 : 0.15)*atr;
   double maxSweep=0.50*atr;
   double priorHi=r[2].high,priorLo=r[2].low;
   for(int i=3;i<=21;i++){priorHi=MathMax(priorHi,r[i].high);priorLo=MathMin(priorLo,r[i].low);}
   if(r[1].low<=priorLo-minSweep && r[1].low>=priorLo-maxSweep
      && r[0].close>priorLo && R2TrendCandle(r[0],true,atr,0.60)) return 1;
   if(r[1].high>=priorHi+minSweep && r[1].high<=priorHi+maxSweep
      && r[0].close<priorHi && R2TrendCandle(r[0],false,atr,0.60)) return -1;
   return 0;
}

int R2BreakRetest(double atr,int direction,const MqlRates &r[],double ema9)
{
   bool buy=direction==1;
   double priorHigh=r[1].high,priorLow=r[1].low;
   for(int i=2;i<=10;i++){priorHigh=MathMax(priorHigh,r[i].high);priorLow=MathMin(priorLow,r[i].low);}
   if(r[0].time==r2RetestReadyBar)
   {
      int ready=r2RetestReadySide;r2RetestReadySide=0;r2RetestReadyBar=0;return ready;
   }
   if(r[0].time==r2ArmHandledBar) return 0;
   if(r2ArmedDirection!=0)
   {
      if(r[0].time>r2ArmedOnBar)
      {
         int retest=R2RetestRule(r[0],r2ArmedLevel,r2ArmedDirection,atr,ema9);
         if(retest!=0){int out=retest;r2ArmedDirection=0;r2ArmedAge=0;r2ArmedLevel=0;r2ArmedOnBar=0;return out;}
      }
   }
   if(r2ArmedDirection==0 && direction!=0)
   {
      if(buy && MathAbs(priorHigh-r2LastArmLevel)>_Point && r[0].close>=priorHigh+0.05*atr)
         {r2ArmedLevel=priorHigh;r2ArmedDirection=1;r2ArmedAge=0;r2ArmedOnBar=r[0].time;r2LastArmLevel=priorHigh;r2LastArmDirection=1;}
      if(!buy && MathAbs(priorLow-r2LastArmLevel)>_Point && r[0].close<=priorLow-0.05*atr)
         {r2ArmedLevel=priorLow;r2ArmedDirection=-1;r2ArmedAge=0;r2ArmedOnBar=r[0].time;r2LastArmLevel=priorLow;r2LastArmDirection=-1;}
   }
   return 0;
}

int R2Exhaustion(double atr,int direction,const MqlRates &r[],double ema9,double e9prev)
{
   if(!MathIsValidNumber(e9prev)) return 0;
   bool buy=direction==1;
   double x=(InpEntryStrength==0 ? 1.25 : 1.75)*atr;
   double priorExtreme=buy ? r[3].low : r[3].high;
   for(int i=4;i<=12;i++) priorExtreme=buy ? MathMin(priorExtreme,r[i].low) : MathMax(priorExtreme,r[i].high);
   bool priorSwing=buy ? (r[1].low<=priorExtreme || r[2].low<=priorExtreme)
                       : (r[1].high>=priorExtreme || r[2].high>=priorExtreme);
   bool displacement=buy ? r[1].close-r[6].close<=-x : r[1].close-r[6].close>=x;
   if(!priorSwing || !displacement || MathAbs(r[0].close-ema9)>0.25*atr
      || !R2TrendCandle(r[0],buy,atr,0.70)) return 0;
   if(buy && r[1].close<=e9prev && r[0].close>ema9) return 1;
   if(!buy && r[1].close>=e9prev && r[0].close<ema9) return -1;
   return 0;
}

int CandidateR2Signal(double atr)
{
   candidateTrend=0;candidateSide=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
   if(InpExperimentMode==0){candidateReason="v24_exact_signal";candidateSide=ProposedSignal(atr);return candidateSide;}
   candidateReason="invalid_atr";
   if(!MathIsValidNumber(atr) || atr<=0) return 0;
   MqlRates r[];
   candidateReason="closed_history_unavailable";
   if(!CopyR2Rates(23,r)) return 0;
   candidateReason="trend_or_context_unavailable";
   int direction=0;double m5atr=0,ema9=0,ema20=0;
   if(!ReadR2Context(direction,m5atr,ema9,ema20)) return 0;
   bool needsTrend=(InpExperimentMode!=3);
   if(needsTrend && direction==0){candidateReason="trend_unaligned";return 0;}
   if((InpExperimentMode==1 || InpExperimentMode==2 || InpExperimentMode==4)
      && !R2M1Aligned(direction,ema9,ema20)){candidateReason="m1_alignment_missing";return 0;}
   if(InpExperimentMode==4 && direction==0){candidateReason="trend_unaligned";return 0;}
   candidateTrend=direction;
   candidateReason="cost_or_chase";
   if(!R2CostGate(r[0],atr)) return 0;
   candidateReason="entry_pattern_absent";
   if(InpExperimentMode==1) candidateSide=R2Pullback(atr,direction,r[0],ema9,ema20);
   else if(InpExperimentMode==2)
   {
      double previousATR[];ArraySetAsSeries(previousATR,true);
      if(CopyBuffer(atrHandle,0,2,3,previousATR)==3)
         candidateSide=R2Compression(atr,direction,r,ema9,previousATR);
   }
   else if(InpExperimentMode==3)
   {
      double fast,slow,past;
      if(ReadClosed(trendFast,1,fast) && ReadClosed(trendSlow,1,slow) && ReadClosed(trendFast,6,past))
         candidateSide=R2RangeReversal(atr,r,fast,slow,past,m5atr);
   }
   else if(InpExperimentMode==4) candidateSide=R2BreakRetest(atr,direction,r,ema9);
   else if(InpExperimentMode==5)
   {
      double e9prev;
      if(ReadClosed(entryFast,2,e9prev)) candidateSide=R2Exhaustion(atr,direction,r,ema9,e9prev);
   }
   if(candidateSide!=0){candidateReason="r2_candidate_signal";candidateTrend=direction;}
   return candidateSide;
}

void ExportCoverageR2()
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
   if(!FrameAdd("r2_native_grid",InpExperimentMode,net,d))return -DBL_MAX;
   for(int k=0;k<monthN;k++)
   {
      double coverage[4];coverage[0]=monthIds[k];coverage[1]=(double)monthTicks[k];
      coverage[2]=(double)monthFirst[k];coverage[3]=(double)monthLast[k];
      if(!FrameAdd("r2_month_coverage",InpExperimentMode,net,coverage))return -DBL_MAX;
   }
   return net;
}

void DrainOptimizationFrames()
{
   if(frameFile==INVALID_HANDLE)return;
   ulong pass;string name;long id;double value;double d[];
   while(FrameNext(pass,name,id,value,d))
   {
      if(name=="r2_month_coverage" && ArraySize(d)==4)
      {
         if(frameMonthFile!=INVALID_HANDLE)FileWrite(frameMonthFile,pass,d[0],d[1],d[2],d[3]);
         continue;
      }
      if(name!="r2_native_grid" || ArraySize(d)!=19)continue;
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
   if(fresh) R2AdvanceArmOnFreshBar();
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
