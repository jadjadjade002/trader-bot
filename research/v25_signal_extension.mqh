// Inlined by hash-guarded build_v25.py. Tester only. No BE/martingale/grid.
input string InpRunTag="v25bench";
input int InpExperimentMode=0; // 0 exact V24, 1 continuation, 2 reclaim, 3 breakout
input int InpEntryStrength=0; // body/ATR .1/.2/.3, close location .6/.7/.8, buffer 0/.05/.1ATR
input bool InpUseGridIndices=false;
input int InpTPGridIndex=2; // {1,1.5,2,3}
int frameFile=INVALID_HANDLE;
int frameMonthFile=INVALID_HANDLE;
int diagnosticFile=INVALID_HANDLE;
string candidateReason="not_evaluated";
int candidateTrend=0,candidateSide=0;
double diagnosticBody=0,diagnosticCloseLocation=0,diagnosticLevel=0;

double EffectiveTPR()
{
   if(!InpUseGridIndices)return InpTakeProfitRRMul;
   double values[4]={1.0,1.5,2.0,3.0};return values[InpTPGridIndex];
}
bool ValidateV25Inputs()
{
   if(InpExperimentMode<0 || InpExperimentMode>3 || InpEntryStrength<0 || InpEntryStrength>2
      || InpTPGridIndex<0 || InpTPGridIndex>3 || InpFadeBreakouts) return false;
   if(!MathIsValidNumber(InpStopLossATRMul) || InpStopLossATRMul<0.5 || InpStopLossATRMul>3.0
      || !MathIsValidNumber(EffectiveTPR()) || EffectiveTPR()<0.5 || EffectiveTPR()>4.0
      || InpMaxHoldBars<15 || InpMaxHoldBars>120) return false;
   return true;
}
bool BenchInit()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION)) return true;
   rawFile=FileOpen(InpRunTag+"_raw.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   diagnosticFile=FileOpen(InpRunTag+"_signals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(rawFile==INVALID_HANDLE || diagnosticFile==INVALID_HANDLE) return false;
   FileWrite(rawFile,"bar","tick_msc","original","closeback","dc_low","dc_high","atr","break_close","retest_open","retest_close","retest_high","retest_low","bid","ask","held_before","cooldown_before","gate","order_attempt","retcode","order_ticket","deal_ticket");
   FileWrite(diagnosticFile,"bar","tick_msc","mode","entry_strength","signal","trend","reason","body_atr","close_location","entry_level","execution_gate","held_before","order_attempt");
   return true;
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
int CandidateSignal(double atr)
{
   candidateTrend=0;candidateSide=0;diagnosticBody=0;diagnosticCloseLocation=0;diagnosticLevel=0;
   if(InpExperimentMode==0)
   {
      candidateReason="v24_exact_signal";
      candidateSide=ProposedSignal(atr);
      return candidateSide;
   }
   candidateReason="invalid_atr";
   if(!MathIsValidNumber(atr) || atr<=0) return 0;
   candidateTrend=ClosedTrendDirection();candidateReason="trend_unaligned";
   if(candidateTrend==0) return 0;
   MqlRates r[];ArraySetAsSeries(r,true);
   candidateReason="closed_history_unavailable";
   if(CopyRates(_Symbol,PERIOD_M1,1,11,r)!=11) return 0;
   double e9;if(!ReadClosed(entryFast,1,e9)) return 0;
   MqlTick q;candidateReason="quote_unavailable";
   if(!SymbolInfoTick(_Symbol,q) || !MathIsValidNumber(q.ask) || !MathIsValidNumber(q.bid)
      || q.bid<=0 || q.ask<q.bid) return 0;
   candidateReason="cost_or_chase";
   if(q.ask-q.bid>0.1*atr || MathAbs((q.ask+q.bid)/2-r[0].close)>0.5*atr) return 0;
   double range=r[0].high-r[0].low;
   candidateReason="zero_or_oversized_candle";
   if(range<=0 || range>2.0*atr) return 0;
   double minBody[3]={0.10,0.20,0.30},minClose[3]={0.60,0.70,0.80},buffer[3]={0.0,0.05,0.10};
   bool buy=candidateTrend==1;
   diagnosticBody=MathAbs(r[0].close-r[0].open)/atr;
   diagnosticCloseLocation=buy?(r[0].close-r[0].low)/range:(r[0].high-r[0].close)/range;
   candidateReason="weak_body_or_close";
   if(diagnosticBody<minBody[InpEntryStrength] || diagnosticCloseLocation<minClose[InpEntryStrength]
      || (buy && r[0].close<=r[0].open) || (!buy && r[0].close>=r[0].open)) return 0;
   double pad=buffer[InpEntryStrength]*atr;
   candidateReason="entry_pattern_absent";
   if(InpExperimentMode==1)
   {
      diagnosticLevel=buy?r[1].high:r[1].low;
      if((buy && r[0].close>e9 && r[0].close>diagnosticLevel+pad)
         || (!buy && r[0].close<e9 && r[0].close<diagnosticLevel-pad)) candidateSide=candidateTrend;
   }
   else if(InpExperimentMode==2)
   {
      diagnosticLevel=e9;
      if((buy && r[0].low<=e9 && r[0].close>e9+pad)
         || (!buy && r[0].high>=e9 && r[0].close<e9-pad)) candidateSide=candidateTrend;
   }
   else if(InpExperimentMode==3)
   {
      diagnosticLevel=buy?r[1].high:r[1].low;
      // r[1..10] = completed shifts 2..11, excludes signal bar r[0].
      for(int i=2;i<11;i++)diagnosticLevel=buy?MathMax(diagnosticLevel,r[i].high):MathMin(diagnosticLevel,r[i].low);
      if((buy && r[0].close>e9 && r[0].close>diagnosticLevel+pad)
         || (!buy && r[0].close<e9 && r[0].close<diagnosticLevel-pad)) candidateSide=candidateTrend;
   }
   if(candidateSide!=0)candidateReason="trend_aligned_entry";
   return candidateSide;
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
      // Diagnostic reads occur after economic execution, never affect its inputs.
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
void ExportCoverage()
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
   d[0]=InpExperimentMode;d[1]=InpStopLossATRMul;d[2]=EffectiveTPR();d[3]=0;d[4]=0.05;
   d[5]=net;d[6]=pos;d[7]=loss;d[8]=ArraySize(pnl);d[9]=wins;
   d[10]=TesterStatistics(STAT_EQUITY_DD);d[11]=TesterStatistics(STAT_EQUITYDD_PERCENT);
   d[12]=TesterStatistics(STAT_PROFIT);d[13]=0;d[14]=0;d[15]=(double)seenTicks;
   d[16]=(double)firstTick;d[17]=(double)lastTick;d[18]=InpEntryStrength;
   if(!FrameAdd("v25_native_grid",InpExperimentMode,net,d))return -DBL_MAX;
   for(int k=0;k<monthN;k++)
   {
      double coverage[4];coverage[0]=monthIds[k];coverage[1]=(double)monthTicks[k];
      coverage[2]=(double)monthFirst[k];coverage[3]=(double)monthLast[k];
      if(!FrameAdd("v25_month_coverage",InpExperimentMode,net,coverage))return -DBL_MAX;
   }
   return net;
}
void DrainOptimizationFrames()
{
   if(frameFile==INVALID_HANDLE)return;
   ulong pass;string name;long id;double value;double d[];
   while(FrameNext(pass,name,id,value,d))
   {
      if(name=="v25_month_coverage" && ArraySize(d)==4)
      {
         if(frameMonthFile!=INVALID_HANDLE)FileWrite(frameMonthFile,pass,d[0],d[1],d[2],d[3]);
         continue;
      }
      if(name!="v25_native_grid" || ArraySize(d)!=19)continue;
      FileWrite(frameFile,pass,d[0],d[1],d[2],d[3],d[4],d[5],d[6],d[7],d[8],d[9],d[10],d[11],d[12],d[13],d[14],d[15],d[16],d[17],d[18]);
   }
   FileFlush(frameFile);
   if(frameMonthFile!=INVALID_HANDLE)FileFlush(frameMonthFile);
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
