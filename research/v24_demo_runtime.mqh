// Inlined by build_v24.py. Status and account guards do not change signal economics.
int trendFast=INVALID_HANDLE,trendSlow=INVALID_HANDLE,trendATR=INVALID_HANDLE;
int entryFast=INVALID_HANDLE,entrySlow=INVALID_HANDLE;
string v24State="STARTING";

bool InitV24Signal()
{
   trendFast=iMA(_Symbol,PERIOD_M5,20,0,MODE_EMA,PRICE_CLOSE);
   trendSlow=iMA(_Symbol,PERIOD_M5,50,0,MODE_EMA,PRICE_CLOSE);
   trendATR=iATR(_Symbol,PERIOD_M5,14);
   entryFast=iMA(_Symbol,PERIOD_M1,9,0,MODE_EMA,PRICE_CLOSE);
   entrySlow=iMA(_Symbol,PERIOD_M1,20,0,MODE_EMA,PRICE_CLOSE);
   return trendFast!=INVALID_HANDLE && trendSlow!=INVALID_HANDLE && trendATR!=INVALID_HANDLE
      && entryFast!=INVALID_HANDLE && entrySlow!=INVALID_HANDLE;
}
void V24Status(string state)
{
   v24State=state;
   Comment("AEGIS V24 | DEMO RESEARCH | XAUUSD M1\n",
           "M5 trend + M1 pullback/reclaim | BE OFF\n",
           "Account: ",AccountInfoInteger(ACCOUNT_LOGIN)," Magic: ",InpMagicNumber,"\n",
           "Lot: ",DoubleToString(InpLotSize,2)," SL: ",DoubleToString(InpStopLossATRMul,2),
           " ATR TP: ",DoubleToString(InpTakeProfitRRMul,2),"R\n",
           "State: ",state,"\nHistorical five-month net negative. Experimental demo only.");
}
void LogV24Health()
{
   PrintFormat("V24 HEALTH Account=%I64d Mode=DEMO Connected=%d AutoTrading=%d EAAllowed=%d AccountTrading=%d AccountExperts=%d Positions=%d State=%s Balance=%.2f Equity=%.2f FreeMargin=%.2f Magic=%I64u SLATR=%.2f TPR=%.2f BE=OFF",
      AccountInfoInteger(ACCOUNT_LOGIN),(int)TerminalInfoInteger(TERMINAL_CONNECTED),
      (int)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED),(int)MQLInfoInteger(MQL_TRADE_ALLOWED),
      (int)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED),(int)AccountInfoInteger(ACCOUNT_TRADE_EXPERT),
      PositionsTotal(),v24State,AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),
      AccountInfoDouble(ACCOUNT_MARGIN_FREE),InpMagicNumber,InpStopLossATRMul,InpTakeProfitRRMul);
}
void OnTimer()
{
   LogV24Health();
}
void LogV24Order(string direction)
{
   uint code=trade.ResultRetcode();
   PrintFormat("V24 ORDER RESPONSE Side=%s Retcode=%u Order=%I64u Deal=%I64u Description=%s",
       direction,code,trade.ResultOrder(),trade.ResultDeal(),trade.ResultRetcodeDescription());
   V24Status((code==TRADE_RETCODE_DONE || code==TRADE_RETCODE_DONE_PARTIAL)
      ? "ORDER_EXECUTED" : "ORDER_RESPONSE_NOT_CONFIRMED_FILLED");
}
