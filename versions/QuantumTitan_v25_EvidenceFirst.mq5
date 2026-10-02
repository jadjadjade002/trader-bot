#property strict
#property version "25.00"
#property description "Experimental XAUUSD M1 R4 state transition with mandatory hard stop and risk vetoes. No proven edge."
#include <Trade/Trade.mqh>

input bool     InpEnableTrading=false;       // Explicit opt-in; research candidate by default.
input ulong    InpTargetAccount=0;           // Optional exact demo account binding.
input datetime InpIndicatorSeedStart=D'2025.08.11 00:00';
input double   InpLots=0.01;
input double   InpStopATR=2.0;               // Hard stop; no break-even or profit lock.
input double   InpMaxRiskPercent=3.0;        // Skip if minimum lot risks more than this.
input double   InpMaxDailyLossPercent=5.0;   // Account-wide equity loss from broker-day start.
input int      InpMaxEntriesPerDay=4;
input double   InpMaxSpreadPoints=40.0;
input int      InpMaxTickAgeSeconds=3;
input double   InpMaxMarginFraction=0.30;
const ulong MAGIC=992500;

CTrade trade;
datetime lastBar=0,lastProcessed=0;
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

bool EntrySession(datetime moment)
{
   MqlDateTime dt; TimeToStruct(moment,dt);
   int minute=dt.hour*60+dt.min;
   return minute>=1080 || minute<117;
}

datetime BrokerDayStart(datetime moment)
{
   MqlDateTime dt; TimeToStruct(moment,dt);
   dt.hour=0; dt.min=0; dt.sec=0;
   return StructToTime(dt);
}

// Indicators use completed bars only. Same EMA/ATR seed and 120-bar regime as R4.
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

bool AnySymbolPosition()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket>0 && PositionGetString(POSITION_SYMBOL)==_Symbol) return true;
   }
   return false;
}

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
      PrintFormat("V25 EXIT ticket=%I64u bars=%d sent=%d retcode=%u %s",ticket,completed,sent,trade.ResultRetcode(),trade.ResultRetcodeDescription());
   }
}

bool DailyLimits(datetime now)
{
   if(!HistorySelect(BrokerDayStart(now),now)) {Print("V25 BLOCK history unavailable");return false;}
   double realized=0.0;
   int entries=0;
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong deal=HistoryDealGetTicket(i);
      if(deal==0) continue;
      long type=HistoryDealGetInteger(deal,DEAL_TYPE);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      realized+=HistoryDealGetDouble(deal,DEAL_PROFIT)+HistoryDealGetDouble(deal,DEAL_COMMISSION)+
                HistoryDealGetDouble(deal,DEAL_SWAP)+HistoryDealGetDouble(deal,DEAL_FEE);
      if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)==MAGIC && HistoryDealGetInteger(deal,DEAL_ENTRY)==DEAL_ENTRY_IN) entries++;
   }
   double dayStartBalance=AccountInfoDouble(ACCOUNT_BALANCE)-realized;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(dayStartBalance<=0 || equity<=0) {Print("V25 BLOCK invalid equity baseline");return false;}
   if(equity-dayStartBalance <= -dayStartBalance*InpMaxDailyLossPercent/100.0)
   {PrintFormat("V25 BLOCK daily loss equity=%.2f start=%.2f",equity,dayStartBalance);return false;}
   if(entries>=InpMaxEntriesPerDay)
   {PrintFormat("V25 BLOCK daily entries=%d",entries);return false;}
   return true;
}

int OnInit()
{
   if(!Authorized() || _Period!=PERIOD_M1 || StringFind(_Symbol,"XAUUSD")!=0) return INIT_PARAMETERS_INCORRECT;
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return INIT_PARAMETERS_INCORRECT;
   if(InpLots<=0 || InpStopATR<=0 || InpMaxRiskPercent<=0 || InpMaxDailyLossPercent<=0 || InpMaxEntriesPerDay<1 ||
      InpMaxSpreadPoints<=0 || InpMaxTickAgeSeconds<1 || InpMaxMarginFraction<=0 || InpMaxMarginFraction>=1) return INIT_PARAMETERS_INCORRECT;
   double minimum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),maximum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX),step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0 || InpLots<minimum || InpLots>maximum || MathAbs(InpLots/step-MathRound(InpLots/step))>1e-7) return INIT_PARAMETERS_INCORRECT;
   trade.SetExpertMagicNumber(MAGIC); trade.SetAsyncMode(false);
   trade.SetDeviationInPoints(20); trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("V25 INIT research-candidate enabled=%d demo-only account=%I64u lot=%.2f hardSL=%.2fATR maxRisk=%.2f%% dailyLoss=%.2f%%",
               InpEnableTrading,AccountInfoInteger(ACCOUNT_LOGIN),InpLots,InpStopATR,InpMaxRiskPercent,InpMaxDailyLossPercent);
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
   if(copied<=0) {lastBar=current;Print("V25 SKIP history unavailable");return;}
   bool bootstrap=(lastProcessed==0);
   for(int i=0;i<copied;i++) Consume(bars[i]);
   lastBar=current;
   if(bootstrap) {PrintFormat("V25 BOOTSTRAP bars=%d. No stale entry.",samples);return;}
   if(copied!=1 || current-lastProcessed!=60) {Print("V25 BLOCK missed bar or gap");return;}
   if(latestDirection==0) return;
   PrintFormat("V25 SIGNAL time=%s dir=%d fast=%.5f slow=%.5f atr=%.5f regime=%.3f",TimeToString(lastProcessed),latestDirection,fast,slow,atr,latestRatio);
   if(!InpEnableTrading) {Print("V25 BLOCK opt-in disabled");return;}
   if(!EntrySession(current)) {Print("V25 BLOCK session");return;}
   if(AnySymbolPosition()) {Print("V25 BLOCK account symbol exposure");return;}
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.ask<=tick.bid || tick.bid<=0) {Print("V25 BLOCK invalid quote");return;}
   long tickAge=(long)(TimeTradeServer()-tick.time);
   if(tickAge<0 || tickAge>InpMaxTickAgeSeconds) {PrintFormat("V25 BLOCK stale/clock quote age=%d",tickAge);return;}
   double spread=(tick.ask-tick.bid)/_Point;
   if(spread>InpMaxSpreadPoints) {PrintFormat("V25 BLOCK spread=%.1f",spread);return;}
   if(!DailyLimits(current)) return;
   double price=(latestDirection>0 ? tick.ask : tick.bid);
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickSize<=0) {Print("V25 BLOCK tick size");return;}
   double raw=price-latestDirection*InpStopATR*atr;
   double sl=NormalizeDouble((latestDirection>0 ? MathFloor(raw/tickSize) : MathCeil(raw/tickSize))*tickSize,_Digits);
   double minStop=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*_Point;
   if((latestDirection>0 && tick.bid-sl<minStop) || (latestDirection<0 && sl-tick.ask<minStop)) {Print("V25 BLOCK broker stop level");return;}
   ENUM_ORDER_TYPE orderType=(latestDirection>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double projectedPnL=0,requiredMargin=0;
   if(!OrderCalcProfit(orderType,_Symbol,InpLots,price,sl,projectedPnL) || projectedPnL>=0)
   {Print("V25 BLOCK risk estimate unavailable");return;}
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(-projectedPnL>equity*InpMaxRiskPercent/100.0)
   {PrintFormat("V25 BLOCK per-trade risk=%.2f cap=%.2f",-projectedPnL,equity*InpMaxRiskPercent/100.0);return;}
   if(!OrderCalcMargin(orderType,_Symbol,InpLots,price,requiredMargin) ||
      requiredMargin>AccountInfoDouble(ACCOUNT_MARGIN_FREE)*InpMaxMarginFraction)
   {Print("V25 BLOCK margin");return;}
   bool sent=(latestDirection>0 ? trade.Buy(InpLots,_Symbol,0,sl,0,"V25 R4 guarded") : trade.Sell(InpLots,_Symbol,0,sl,0,"V25 R4 guarded"));
   uint retcode=trade.ResultRetcode();
   bool filled=sent && (retcode==TRADE_RETCODE_DONE || retcode==TRADE_RETCODE_DONE_PARTIAL);
   PrintFormat("V25 ENTRY sent=%d filled=%d retcode=%u deal=%I64u fill=%.5f sl=%.5f projectedLoss=%.2f %s",
               sent,filled,retcode,trade.ResultDeal(),trade.ResultPrice(),sl,-projectedPnL,trade.ResultRetcodeDescription());
}

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal)) return;
   if((ulong)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=MAGIC || HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=_Symbol) return;
   PrintFormat("V25 DEAL id=%I64u entry=%d reason=%d profit=%.2f commission=%.2f swap=%.2f fee=%.2f",
      trans.deal,(int)HistoryDealGetInteger(trans.deal,DEAL_ENTRY),(int)HistoryDealGetInteger(trans.deal,DEAL_REASON),
      HistoryDealGetDouble(trans.deal,DEAL_PROFIT),HistoryDealGetDouble(trans.deal,DEAL_COMMISSION),
      HistoryDealGetDouble(trans.deal,DEAL_SWAP),HistoryDealGetDouble(trans.deal,DEAL_FEE));
}
