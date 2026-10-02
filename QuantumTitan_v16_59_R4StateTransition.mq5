#property strict
#property version "16.59"
#property description "Demo research: R4 EMA6/24 state transition, three completed bars, no BE/trailing"
#include <Trade/Trade.mqh>

input ulong InpTargetAccount=0;
input datetime InpIndicatorSeedStart=D'2025.08.11 00:00';
input bool InpEmergencyStop=false; // Optional 5 ATR disaster stop changes nominal research outcomes.
const ulong MAGIC=991659;
const double LOTS=0.01;
CTrade trade;
datetime lastBar=0,lastProcessed=0,historyStart=0;
int samples=0,ringCount=0,ringNext=0;
double fast=0,slow=0,atr=0,sumFast=0,sumSlow=0,sumTR=0,previousClose=0;
double atrRing[120];
datetime timeRing[120];
int latestDirection=0;
double latestRatio=0;

bool Authorized()
{
   return AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO &&
      (InpTargetAccount==0 || (ulong)AccountInfoInteger(ACCOUNT_LOGIN)==InpTargetAccount);
}

bool EntrySession(datetime when)
{
   MqlDateTime dt; TimeToStruct(when,dt);
   int minute=dt.hour*60+dt.min;
   return minute>=1080 || minute<117;
}

// Chronological updates use only completed bars. Seeds match analyze_r4.py.
void Consume(const MqlRates &bar)
{
   latestDirection=0;
   double priorFast=fast,priorSlow=slow;
   double tr=bar.high-bar.low;
   if(samples>0) tr=MathMax(tr,MathMax(MathAbs(bar.high-previousClose),MathAbs(bar.low-previousClose)));
   samples++;
   if(samples<=6) {sumFast+=bar.close; if(samples==6) fast=sumFast/6.0;}
   else fast=(2.0/7.0)*bar.close+(5.0/7.0)*fast;
   if(samples<=24) {sumSlow+=bar.close; if(samples==24) slow=sumSlow/24.0;}
   else slow=(2.0/25.0)*bar.close+(23.0/25.0)*slow;
   if(samples<=14) {sumTR+=tr; if(samples==14) atr=sumTR/14.0;}
   else atr=(atr*13.0+tr)/14.0;
   previousClose=bar.close;
   lastProcessed=bar.time;
   if(samples<14) return;
   atrRing[ringNext]=atr; timeRing[ringNext]=bar.time;
   ringNext=(ringNext+1)%120; ringCount=MathMin(120,ringCount+1);
   if(ringCount<120 || samples<25) return;
   double sorted[120];
   for(int j=0;j<120;j++)
   {
      int slot=(ringNext+j)%120;
      sorted[j]=atrRing[slot];
      if(!MathIsValidNumber(sorted[j]) || sorted[j]<=0) return;
      if(j>0 && timeRing[slot]-timeRing[(ringNext+j-1)%120]!=60) return;
   }
   ArraySort(sorted);
   double median=(sorted[59]+sorted[60])/2.0;
   latestRatio=atr/median;
   if(latestRatio<0.5 || latestRatio>1.5) return;
   if(MathAbs(bar.close-slow)>0.35*atr || bar.high-bar.low>1.5*atr) return;
   if(fast>slow && priorFast<=priorSlow) latestDirection=1;
   if(fast<slow && priorFast>=priorSlow) latestDirection=-1;
}

int OwnPositions()
{
   int count=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(PositionGetTicket(i)==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol && (ulong)PositionGetInteger(POSITION_MAGIC)==MAGIC) count++;
   }
   return count;
}

// Runs every tick, including after a failed close. Restarts recover age from broker position time.
void CloseMaturePositions()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || PositionGetString(POSITION_SYMBOL)!=_Symbol || (ulong)PositionGetInteger(POSITION_MAGIC)!=MAGIC) continue;
      datetime entered=(datetime)PositionGetInteger(POSITION_TIME);
      int completed=iBarShift(_Symbol,PERIOD_M1,entered,false);
      if(completed<3) continue;
      bool sent=trade.PositionClose(ticket);
      uint result=trade.ResultRetcode();
      PrintFormat("R4 EXIT ticket=%I64u held_bars=%d sent=%d retcode=%u detail=%s",ticket,completed,sent,result,trade.ResultRetcodeDescription());
   }
}

int OnInit()
{
   if(!Authorized() || _Period!=PERIOD_M1 || StringFind(_Symbol,"XAUUSD")!=0) return INIT_PARAMETERS_INCORRECT;
   // Netting cannot isolate another strategy's position on this symbol.
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return INIT_PARAMETERS_INCORRECT;
   double minimum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),maximum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX),step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0 || LOTS<minimum || LOTS>maximum || MathAbs(LOTS/step-MathRound(LOTS/step))>1e-7) return INIT_PARAMETERS_INCORRECT;
   trade.SetExpertMagicNumber(MAGIC); trade.SetAsyncMode(false);
   trade.SetDeviationInPoints(20); trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("R4 INIT demo-only magic=%I64u lot=%.2f seed=%s emergency_5ATR=%d. Live exit next available tick after 3 completed bars; future gaps unknowable.",MAGIC,LOTS,TimeToString(InpIndicatorSeedStart),InpEmergencyStop);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(!Authorized()) return;
   CloseMaturePositions();
   datetime current=iTime(_Symbol,PERIOD_M1,0);
   if(current<=0 || current==lastBar) return;
   MqlRates bars[];
   ArraySetAsSeries(bars,false);
   datetime start=(lastProcessed==0 ? InpIndicatorSeedStart : lastProcessed+1);
   int copied=CopyRates(_Symbol,PERIOD_M1,start,current-1,bars);
   if(copied<=0)
   {
      lastBar=current;
      Print("R4 SKIP history unavailable at first observed bar tick");
      return; // Next bar catches history up, but cannot open a stale signal.
   }
   bool bootstrap=(lastProcessed==0);
   if(bootstrap) historyStart=bars[0].time;
   for(int i=0;i<copied;i++) Consume(bars[i]);
   lastBar=current;
   if(bootstrap)
   {
      PrintFormat("R4 BOOTSTRAP requested=%s actual=%s bars=%d. EMA/ATR seed parity requires identical input history.",TimeToString(InpIndicatorSeedStart),TimeToString(historyStart),samples);
      return; // Attaching mid-bar must not cause a late entry.
   }
   if(copied!=1 || current-lastProcessed!=60) {Print("R4 SKIP missed bar or gap");return;}
   if(latestDirection==0) return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.ask<=tick.bid || tick.bid<=0) return;
   double spread=(tick.ask-tick.bid)/_Point;
   PrintFormat("R4 SIGNAL bar=%s dir=%d EMA6=%.8f EMA24=%.8f ATR14=%.8f ratio=%.6f spread=%.2f",TimeToString(lastProcessed),latestDirection,fast,slow,atr,latestRatio,spread);
   if(!EntrySession(current)) {Print("R4 BLOCK session");return;}
   if(spread>40.0) {Print("R4 BLOCK spread");return;}
   if(OwnPositions()>0) {Print("R4 BLOCK existing position");return;}
   double price=(latestDirection>0 ? tick.ask : tick.bid),sl=0;
   if(InpEmergencyStop)
   {
      double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
      if(tickSize<=0) return;
      double raw=price-latestDirection*5.0*atr;
      sl=NormalizeDouble((latestDirection>0 ? MathFloor(raw/tickSize) : MathCeil(raw/tickSize))*tickSize,_Digits);
      double minStop=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*_Point;
      if((latestDirection>0 && tick.bid-sl<minStop) || (latestDirection<0 && sl-tick.ask<minStop)) {Print("R4 BLOCK emergency stop constraints");return;}
   }
   bool sent=(latestDirection>0 ? trade.Buy(LOTS,_Symbol,0,sl,0,"R4 EMA6/24 3bars") : trade.Sell(LOTS,_Symbol,0,sl,0,"R4 EMA6/24 3bars"));
   PrintFormat("R4 ENTRY sent=%d retcode=%u order=%I64u deal=%I64u fill=%.8f sl=%.8f detail=%s",sent,trade.ResultRetcode(),trade.ResultOrder(),trade.ResultDeal(),trade.ResultPrice(),sl,trade.ResultRetcodeDescription());
}

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal)) return;
   if((ulong)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=MAGIC || HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=_Symbol) return;
   PrintFormat("R4 DEAL id=%I64u entry=%d reason=%d price=%.8f volume=%.2f profit=%.2f commission=%.2f swap=%.2f fee=%.2f",trans.deal,(int)HistoryDealGetInteger(trans.deal,DEAL_ENTRY),(int)HistoryDealGetInteger(trans.deal,DEAL_REASON),HistoryDealGetDouble(trans.deal,DEAL_PRICE),HistoryDealGetDouble(trans.deal,DEAL_VOLUME),HistoryDealGetDouble(trans.deal,DEAL_PROFIT),HistoryDealGetDouble(trans.deal,DEAL_COMMISSION),HistoryDealGetDouble(trans.deal,DEAL_SWAP),HistoryDealGetDouble(trans.deal,DEAL_FEE));
}
