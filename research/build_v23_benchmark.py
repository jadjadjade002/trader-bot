"""Generate tester-only telemetry wrapper from the immutable deployed V23 source."""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'AegisPredator_v23.mq5').read_bytes()
assert hashlib.sha256(source).hexdigest().upper() == 'C19A29A45925C21305D6B1A8FE4616B8AEEDF1A487B0D278EDAD0880409EDFB0'
text = source.decode('utf-8-sig')
text = text.replace('int OnInit()\n{', 'int OnInit()\n{\n   if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;\n   if(!BenchInit()) return INIT_FAILED;')
text = text.replace('void OnTick()\n{', 'void OriginalOnTick()\n{')
text = text.replace('if(prevBar == 0) // First tick on attach: wait for completed bar\n      return;', 'if(prevBar == 0) // First tick on attach: wait for completed bar\n      { benchGate="attach"; return; }')
text = text.replace('if(HasOpenPosition())\n      return;', 'if(HasOpenPosition())\n      { benchGate="holding"; return; }')
text = text.replace('if(IsCircuitBreakerActive())\n      return;', 'if(IsCircuitBreakerActive())\n      { benchGate="breaker"; return; }')
text = text.replace('if(dt.hour < InpStartHour || dt.hour >= InpEndHour)\n         return;', 'if(dt.hour < InpStartHour || dt.hour >= InpEndHour)\n         { benchGate="session"; return; }')
text = text.replace('if(signal == 0)\n      return;', 'if(signal == 0)\n      { benchGate="no_signal"; return; }')
text = text.replace('if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_BUY, InpLotSize, ask)) return;', 'if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_BUY, InpLotSize, ask)) {benchGate="margin";return;}')
text = text.replace('if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_SELL, InpLotSize, bid)) return;', 'if(InpEnableMarginGuard && !CheckMargin(ORDER_TYPE_SELL, InpLotSize, bid)) {benchGate="margin";return;}')
text = text.replace('if(trade.Buy(', 'benchAttempt=true;benchGate="attempt";\n      if(trade.Buy(').replace('if(trade.Sell(', 'benchAttempt=true;benchGate="attempt";\n      if(trade.Sell(')
text = text.replace('&& retestClose > retestOpen)', '&& (InpRequireCloseBackInside ? (retestClose > donchianLow && retestClose < donchianHigh) : retestClose > retestOpen))')
text = text.replace('&& retestClose < retestOpen)', '&& (InpRequireCloseBackInside ? (retestClose > donchianLow && retestClose < donchianHigh) : retestClose < retestOpen))')
prefix = r'''
// Generated research harness. Trading core copied from frozen production source.
input bool InpRequireCloseBackInside = false;
input string InpRunTag = "bench";
string benchGate="none";
bool benchAttempt=false;
int rawFile = INVALID_HANDLE;
datetime observedBar = 0;
long seenTicks = 0, firstTick = 0, lastTick = 0;
int monthIds[12];
double monthPeak[12], monthDD[12], monthDDPct[12];
long monthTicks[12], monthFirst[12], monthLast[12];
int monthN = 0;
double overallPeak=0, overallDD=0;

bool BenchInit()
{
   rawFile=FileOpen(InpRunTag+"_raw.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(rawFile==INVALID_HANDLE) return false;
   FileWrite(rawFile,"bar","tick_msc","original","closeback","dc_low","dc_high","atr","break_close","retest_open","retest_close","retest_high","retest_low","bid","ask","held_before","cooldown_before","gate","order_attempt","retcode","order_ticket","deal_ticket");
   return true;
}
void ObserveEquity()
{
   MqlTick t; if(!SymbolInfoTick(_Symbol,t)) return;
   MqlDateTime d; TimeToStruct(t.time,d); int id=d.year*100+d.mon;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(overallPeak==0) overallPeak=eq;
   overallPeak=MathMax(overallPeak,eq); overallDD=MathMax(overallDD,overallPeak-eq);
   int k=monthN-1;
   if(k<0 || monthIds[k]!=id)
   {
      if(monthN>=12) return;
      k=monthN++; monthIds[k]=id; monthPeak[k]=eq; monthFirst[k]=t.time_msc;
   }
   monthPeak[k]=MathMax(monthPeak[k],eq);
   monthDD[k]=MathMax(monthDD[k],monthPeak[k]-eq);
   if(monthPeak[k]>0) monthDDPct[k]=MathMax(monthDDPct[k],100*(monthPeak[k]-eq)/monthPeak[k]);
   monthLast[k]=t.time_msc;
}
void OnTick()
{
   MqlTick tick; SymbolInfoTick(_Symbol,tick);
   if(firstTick==0) firstTick=tick.time_msc;
   lastTick=tick.time_msc; seenTicks++;
   ObserveEquity();
   if(monthN>0) monthTicks[monthN-1]++;
   datetime bar=iTime(_Symbol,PERIOD_M1,0);
   bool fresh=(bar>0 && bar!=observedBar);
   int orig=0, inside=0; double lo=0,hi=0,atr=0,bc=0,ro=0,rc=0,rh=0,rl=0;
   bool held=false; datetime cd=cooldownUntil;
   if(fresh)
   {
      observedBar=bar; held=HasOpenPosition();
      MqlRates r[]; double a[]; ArraySetAsSeries(r,true);
      int n=InpDonchianPeriod+3;
      if(CopyRates(_Symbol,PERIOD_M1,1,n,r)==n && CopyBuffer(atrHandle,0,1,1,a)==1 && a[0]>0)
      {
         atr=a[0]; hi=r[2].high; lo=r[2].low;
         for(int b=3;b<=InpDonchianPeriod+1;b++){hi=MathMax(hi,r[b].high);lo=MathMin(lo,r[b].low);}
         bc=r[1].close;ro=r[0].open;rc=r[0].close;rh=r[0].high;rl=r[0].low;
         if(bc>hi && rl>=hi-.5*atr){if(rc>ro)orig=1;if(rc>lo && rc<hi)inside=1;}
         else if(bc<lo && rh<=lo+.5*atr){if(rc<ro)orig=-1;if(rc>lo && rc<hi)inside=-1;}
      }
   }
   benchGate="no_new_bar";benchAttempt=false;
   OriginalOnTick();
   ObserveEquity();
   if(fresh)
      FileWrite(rawFile,TimeToString(bar,TIME_DATE|TIME_SECONDS),tick.time_msc,orig,inside,lo,hi,atr,bc,ro,rc,rh,rl,tick.bid,tick.ask,held,cd,benchGate,benchAttempt,benchAttempt?trade.ResultRetcode():0,benchAttempt?trade.ResultOrder():0,benchAttempt?trade.ResultDeal():0);
}
double OnTester()
{
   ObserveEquity();
   if(rawFile!=INVALID_HANDLE){FileClose(rawFile);rawFile=INVALID_HANDLE;}
   int f=FileOpen(InpRunTag+"_deals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   FileWrite(f,"ticket","position","time_msc","type","entry","reason","magic","symbol","volume","price","profit","commission","swap","fee","comment");
   bool historyOK=HistorySelect(0,TimeCurrent());
   if(historyOK)
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong t=HistoryDealGetTicket(i);
      FileWrite(f,t,HistoryDealGetInteger(t,DEAL_POSITION_ID),HistoryDealGetInteger(t,DEAL_TIME_MSC),HistoryDealGetInteger(t,DEAL_TYPE),HistoryDealGetInteger(t,DEAL_ENTRY),HistoryDealGetInteger(t,DEAL_REASON),HistoryDealGetInteger(t,DEAL_MAGIC),HistoryDealGetString(t,DEAL_SYMBOL),HistoryDealGetDouble(t,DEAL_VOLUME),HistoryDealGetDouble(t,DEAL_PRICE),HistoryDealGetDouble(t,DEAL_PROFIT),HistoryDealGetDouble(t,DEAL_COMMISSION),HistoryDealGetDouble(t,DEAL_SWAP),HistoryDealGetDouble(t,DEAL_FEE),HistoryDealGetString(t,DEAL_COMMENT));
   }
   FileClose(f);
   f=FileOpen(InpRunTag+"_equity.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   FileWrite(f,"month","observed_ticks","first_msc","last_msc","observed_equity_dd","observed_equity_dd_pct");
   for(int k=0;k<monthN;k++) FileWrite(f,monthIds[k],monthTicks[k],monthFirst[k],monthLast[k],monthDD[k],monthDDPct[k]);
   FileClose(f);
   f=FileOpen(InpRunTag+"_spec.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   FileWrite(f,"key","value");
   FileWrite(f,"symbol",_Symbol);FileWrite(f,"first_tick",firstTick);FileWrite(f,"last_tick",lastTick);FileWrite(f,"observed_ticks",seenTicks);
   FileWrite(f,"history_export_ok",historyOK);
   FileWrite(f,"contract_size",SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE));
   FileWrite(f,"tick_size",SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE));
   FileWrite(f,"tick_value_profit",SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE_PROFIT));
   FileWrite(f,"tick_value_loss",SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE_LOSS));
   FileWrite(f,"volume_min",SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN));
   FileWrite(f,"volume_max",SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX));
   FileWrite(f,"volume_step",SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP));
   FileWrite(f,"stops_level",SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL));
   FileWrite(f,"freeze_level",SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL));
   FileWrite(f,"calc_mode",SymbolInfoInteger(_Symbol,SYMBOL_TRADE_CALC_MODE));
   FileWrite(f,"swap_mode",SymbolInfoInteger(_Symbol,SYMBOL_SWAP_MODE));
   FileWrite(f,"swap_long",SymbolInfoDouble(_Symbol,SYMBOL_SWAP_LONG));
   FileWrite(f,"swap_short",SymbolInfoDouble(_Symbol,SYMBOL_SWAP_SHORT));
   FileWrite(f,"margin_initial",SymbolInfoDouble(_Symbol,SYMBOL_MARGIN_INITIAL));
   FileWrite(f,"margin_maintenance",SymbolInfoDouble(_Symbol,SYMBOL_MARGIN_MAINTENANCE));
   FileWrite(f,"account_margin_mode",AccountInfoInteger(ACCOUNT_MARGIN_MODE));
   FileWrite(f,"stopout_mode",AccountInfoInteger(ACCOUNT_MARGIN_SO_MODE));
   FileWrite(f,"stopout_level",AccountInfoDouble(ACCOUNT_MARGIN_SO_SO));
   FileWrite(f,"leverage",AccountInfoInteger(ACCOUNT_LEVERAGE));
   FileWrite(f,"final_balance",AccountInfoDouble(ACCOUNT_BALANCE));
   FileWrite(f,"final_equity",AccountInfoDouble(ACCOUNT_EQUITY));
   FileWrite(f,"observed_overall_equity_dd",overallDD);
   FileClose(f);
   return AccountInfoDouble(ACCOUNT_BALANCE);
}
'''
text = text.replace('//--- Input Parameters', prefix+'\n//--- Input Parameters', 1)
text = text.replace('void OnDeinit(const int reason)\n{', 'void OnDeinit(const int reason)\n{\n   if(rawFile!=INVALID_HANDLE){FileClose(rawFile);rawFile=INVALID_HANDLE;}')
(ROOT/'research/V23_BacktestBenchmark.mq5').write_text(text,encoding='utf-8')
print('Generated tester-only V23 harness from frozen source.')
