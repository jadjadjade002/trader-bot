// Inlined mechanically into the isolated tester harness.
input int InpExperimentMode=0; // 0 VM fade, 1 normal, 2 proposed
input double InpBETriggerR=0.0; // zero disables BE
input double InpBELockR=0.05;
input bool InpUseGridIndices=false;
input int InpTPGridIndex=0;
input int InpBEGridIndex=0;
int trendFast=INVALID_HANDLE,trendSlow=INVALID_HANDLE,trendATR=INVALID_HANDLE;
int entryFast=INVALID_HANDLE,entrySlow=INVALID_HANDLE;
int frameFile=INVALID_HANDLE;
long beModifyAttempts=0,beModifyRejected=0;
ulong bePosition=0;
double beInitialRisk=0;

struct PathObservation
{
   ulong position;
   long opened;
   double entry,risk,mfe,mae;
   long mfeTime,maeTime;
};
PathObservation paths[];

double EffectiveTPR()
{
   if(!InpUseGridIndices)return InpTakeProfitRRMul;
   double values[4]={1.0,1.5,2.0,3.0};return values[InpTPGridIndex];
}
double EffectiveBER()
{
   if(!InpUseGridIndices)return InpBETriggerR;
   double values[3]={0.0,0.8,1.2};return values[InpBEGridIndex];
}

bool InitExperiment()
{
   if(InpTPGridIndex<0 || InpTPGridIndex>3 || InpBEGridIndex<0 || InpBEGridIndex>2) return false;
   double trigger=EffectiveBER();
   if(InpExperimentMode<0 || InpExperimentMode>2 || trigger<0 || InpBELockR<0
      || (trigger>0 && trigger<=InpBELockR)) return false;
   if((InpExperimentMode==0 && !InpFadeBreakouts) || (InpExperimentMode==1 && InpFadeBreakouts)) return false;
   if(InpExperimentMode!=2) return true;
   trendFast=iMA(_Symbol,PERIOD_M5,20,0,MODE_EMA,PRICE_CLOSE);
   trendSlow=iMA(_Symbol,PERIOD_M5,50,0,MODE_EMA,PRICE_CLOSE);
   trendATR=iATR(_Symbol,PERIOD_M5,14);
   entryFast=iMA(_Symbol,PERIOD_M1,9,0,MODE_EMA,PRICE_CLOSE);
   entrySlow=iMA(_Symbol,PERIOD_M1,20,0,MODE_EMA,PRICE_CLOSE);
   return trendFast!=INVALID_HANDLE && trendSlow!=INVALID_HANDLE && trendATR!=INVALID_HANDLE
      && entryFast!=INVALID_HANDLE && entrySlow!=INVALID_HANDLE;
}
void ReleaseExperiment()
{
   if(trendFast!=INVALID_HANDLE) IndicatorRelease(trendFast);
   if(trendSlow!=INVALID_HANDLE) IndicatorRelease(trendSlow);
   if(trendATR!=INVALID_HANDLE) IndicatorRelease(trendATR);
   if(entryFast!=INVALID_HANDLE) IndicatorRelease(entryFast);
   if(entrySlow!=INVALID_HANDLE) IndicatorRelease(entrySlow);
}
bool ReadClosed(int handle,int shift,double &value)
{
   double a[];
   if(CopyBuffer(handle,0,shift,1,a)!=1 || !MathIsValidNumber(a[0])) return false;
   value=a[0];return true;
}
int ProposedSignal(double atr)
{
   double fast,slow,past,m5atr,e9,e20;
   if(!ReadClosed(trendFast,1,fast) || !ReadClosed(trendSlow,1,slow)
      || !ReadClosed(trendFast,6,past) || !ReadClosed(trendATR,1,m5atr)
      || !ReadClosed(entryFast,1,e9) || !ReadClosed(entrySlow,1,e20) || m5atr<=0) return 0;
   MqlRates r[];ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,PERIOD_M1,1,1,r)!=1) return 0;
   MqlTick quote;if(!SymbolInfoTick(_Symbol,quote)) return 0;
   if(quote.ask-quote.bid>0.1*atr || MathAbs((quote.ask+quote.bid)/2-r[0].close)>0.5*atr) return 0;
   if(fast>slow && fast>past && fast-slow>=0.1*m5atr && e9>e20
      && r[0].low<=e9 && r[0].close>e9 && r[0].close>r[0].open) return 1;
   if(fast<slow && fast<past && slow-fast>=0.1*m5atr && e9<e20
      && r[0].high>=e9 && r[0].close<e9 && r[0].close<r[0].open) return -1;
   return 0;
}
void ManageBreakEven()
{
   double trigger=EffectiveBER();
   if(trigger<=0) return;
   bool found=false;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(!posInfo.SelectByIndex(i) || posInfo.Symbol()!=_Symbol || posInfo.Magic()!=InpMagicNumber) continue;
      found=true;
      if(bePosition!=posInfo.Ticket())
      {
         bePosition=posInfo.Ticket();
         beInitialRisk=MathAbs(posInfo.PriceOpen()-posInfo.StopLoss());
      }
      if(beInitialRisk<=0 || posInfo.StopLoss()<=0) continue;
      MqlTick q;if(!SymbolInfoTick(_Symbol,q)) continue;
      bool buy=posInfo.PositionType()==POSITION_TYPE_BUY;
      double gain=buy?q.bid-posInfo.PriceOpen():posInfo.PriceOpen()-q.ask;
      if(gain<trigger*beInitialRisk) continue;
      double size=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
      if(size<=0) continue;
      double stop=buy?MathFloor((posInfo.PriceOpen()+InpBELockR*beInitialRisk)/size)*size:
                       MathCeil((posInfo.PriceOpen()-InpBELockR*beInitialRisk)/size)*size;
      stop=NormalizeDouble(stop,_Digits);
      if((buy && stop<=posInfo.StopLoss()) || (!buy && stop>=posInfo.StopLoss())) continue;
      double bound=MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),
                           SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))*_Point;
      if((buy && q.bid-stop<=bound) || (!buy && stop-q.ask<=bound)) continue;
      beModifyAttempts++;
      if(!trade.PositionModify(posInfo.Ticket(),stop,posInfo.TakeProfit())
         || (trade.ResultRetcode()!=TRADE_RETCODE_DONE && trade.ResultRetcode()!=TRADE_RETCODE_NO_CHANGES))
         beModifyRejected++;
   }
   if(!found){bePosition=0;beInitialRisk=0;}
}
void ObservePath()
{
   if(MQLInfoInteger(MQL_OPTIMIZATION)) return;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(!posInfo.SelectByIndex(i) || posInfo.Symbol()!=_Symbol || posInfo.Magic()!=InpMagicNumber) continue;
      ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      int k=-1;
      for(int j=ArraySize(paths)-1;j>=0;j--) if(paths[j].position==id){k=j;break;}
      if(k<0)
      {
         k=ArraySize(paths);ArrayResize(paths,k+1);
         paths[k].position=id;paths[k].opened=posInfo.Time();paths[k].entry=posInfo.PriceOpen();
         paths[k].risk=MathAbs(posInfo.PriceOpen()-posInfo.StopLoss());
         paths[k].mfe=0;paths[k].mae=0;paths[k].mfeTime=0;paths[k].maeTime=0;
      }
      MqlTick q;if(!SymbolInfoTick(_Symbol,q)) continue;
      double move=posInfo.PositionType()==POSITION_TYPE_BUY?q.bid-paths[k].entry:paths[k].entry-q.ask;
      if(move>paths[k].mfe){paths[k].mfe=move;paths[k].mfeTime=q.time_msc;}
      if(-move>paths[k].mae){paths[k].mae=-move;paths[k].maeTime=q.time_msc;}
   }
}
void ExportPaths()
{
   int f=FileOpen(InpRunTag+"_paths.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE)return;
   FileWrite(f,"position","opened","entry","initial_risk","mfe_price_sampled","mae_price_sampled","mfe_time_msc","mae_time_msc");
   for(int i=0;i<ArraySize(paths);i++) FileWrite(f,paths[i].position,paths[i].opened,paths[i].entry,paths[i].risk,
      paths[i].mfe,paths[i].mae,paths[i].mfeTime,paths[i].maeTime);
   FileClose(f);
   f=FileOpen(InpRunTag+"_be.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f!=INVALID_HANDLE){FileWrite(f,"modify_attempts","modify_rejected");FileWrite(f,beModifyAttempts,beModifyRejected);FileClose(f);}
}
double ExportOptimizationFrame()
{
   double pnl[];ulong ids[];
   if(!HistorySelect(0,TimeCurrent())) return -DBL_MAX;
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong t=HistoryDealGetTicket(i);
      ENUM_DEAL_TYPE type=(ENUM_DEAL_TYPE)HistoryDealGetInteger(t,DEAL_TYPE);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      ulong id=(ulong)HistoryDealGetInteger(t,DEAL_POSITION_ID);int k=-1;
      for(int j=ArraySize(ids)-1;j>=0;j--)if(ids[j]==id){k=j;break;}
      if(k<0){k=ArraySize(ids);ArrayResize(ids,k+1);ArrayResize(pnl,k+1);ids[k]=id;pnl[k]=0;}
      pnl[k]+=HistoryDealGetDouble(t,DEAL_PROFIT)+HistoryDealGetDouble(t,DEAL_COMMISSION)
             +HistoryDealGetDouble(t,DEAL_SWAP)+HistoryDealGetDouble(t,DEAL_FEE);
   }
   double net=0,pos=0,loss=0;int wins=0;
   for(int i=0;i<ArraySize(pnl);i++){net+=pnl[i];if(pnl[i]>0){pos+=pnl[i];wins++;}else loss-=pnl[i];}
   double d[18];
   d[0]=InpExperimentMode;d[1]=InpStopLossATRMul;d[2]=EffectiveTPR();d[3]=EffectiveBER();
   d[4]=InpBELockR;d[5]=net;d[6]=pos;d[7]=loss;d[8]=ArraySize(pnl);d[9]=wins;
   d[10]=TesterStatistics(STAT_EQUITY_DD);d[11]=TesterStatistics(STAT_EQUITYDD_PERCENT);
   d[12]=TesterStatistics(STAT_PROFIT);d[13]=(double)beModifyAttempts;d[14]=(double)beModifyRejected;
   d[15]=(double)seenTicks;
   d[16]=(double)firstTick;d[17]=(double)lastTick;
   if(!FrameAdd("v23_native_grid",InpExperimentMode,net,d)) return -DBL_MAX;
   return net;
}
void DrainOptimizationFrames()
{
   if(frameFile==INVALID_HANDLE)return;
   ulong pass;string name;long id;double value;double d[];
   while(FrameNext(pass,name,id,value,d))
   {
      if(name!="v23_native_grid" || ArraySize(d)!=18) continue;
      FileWrite(frameFile,pass,d[0],d[1],d[2],d[3],d[4],d[5],d[6],d[7],d[8],d[9],d[10],d[11],d[12],d[13],d[14],d[15],d[16],d[17]);
   }
   FileFlush(frameFile);
}
void OnTesterInit()
{
   frameFile=FileOpen(InpRunTag+"_optimization.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(frameFile!=INVALID_HANDLE)FileWrite(frameFile,"pass","mode","sl_atr","tp_r","be_r","be_lock_r","net","gross_net_wins","gross_net_losses","positions","wins","equity_dd","equity_dd_pct","native_net","be_attempts","be_rejected","observed_ticks","first_tick_msc","last_tick_msc");
}
void OnTesterPass(){DrainOptimizationFrames();}
void OnTesterDeinit(){DrainOptimizationFrames();if(frameFile!=INVALID_HANDLE){FileClose(frameFile);frameFile=INVALID_HANDLE;}}
