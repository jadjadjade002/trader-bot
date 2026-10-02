#property strict
#property script_show_inputs
#property description "Read-only XAUUSD contract/risk probe. No orders, no file writes."

input double InpCandidateLots=0.01;
input double InpStopATR=2.0;

void OnStart()
{
   if(StringFind(_Symbol,"XAUUSD")!=0 || InpCandidateLots<=0 || InpStopATR<=0)
   {
      Print("V25_PROBE INVALID symbol or inputs");
      return;
   }
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.bid<=0 || tick.ask<=tick.bid)
   {
      Print("V25_PROBE NO_QUOTE");
      return;
   }
   int handle=iATR(_Symbol,PERIOD_M1,14);
   if(handle==INVALID_HANDLE) {Print("V25_PROBE NO_ATR");return;}
   double values[];
   int copied=CopyBuffer(handle,0,1,1,values);
   IndicatorRelease(handle);
   if(copied!=1 || values[0]<=0) {Print("V25_PROBE NO_CLOSED_ATR");return;}
   double minimum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maximum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double contract=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE);
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double tickLossValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE_LOSS);
   double distance=InpStopATR*values[0];
   double minLoss=0,minMargin=0,candidateLoss=0,candidateMargin=0;
   bool minLossOk=minimum>0 && OrderCalcProfit(ORDER_TYPE_BUY,_Symbol,minimum,tick.ask,tick.ask-distance,minLoss);
   bool minMarginOk=minimum>0 && OrderCalcMargin(ORDER_TYPE_BUY,_Symbol,minimum,tick.ask,minMargin);
   bool validCandidate=step>0 && InpCandidateLots>=minimum && InpCandidateLots<=maximum &&
                       MathAbs(InpCandidateLots/step-MathRound(InpCandidateLots/step))<1e-7;
   bool candidateLossOk=validCandidate && OrderCalcProfit(ORDER_TYPE_BUY,_Symbol,InpCandidateLots,tick.ask,tick.ask-distance,candidateLoss);
   bool candidateMarginOk=validCandidate && OrderCalcMargin(ORDER_TYPE_BUY,_Symbol,InpCandidateLots,tick.ask,candidateMargin);
   PrintFormat("V25_PROBE server=%s symbol=%s demo=%d currency=%s equity=%.2f leverage=%d",
      AccountInfoString(ACCOUNT_SERVER),_Symbol,AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO,
      AccountInfoString(ACCOUNT_CURRENCY),AccountInfoDouble(ACCOUNT_EQUITY),AccountInfoInteger(ACCOUNT_LEVERAGE));
   PrintFormat("V25_PROBE contract=%.8f min_lot=%.4f max_lot=%.4f lot_step=%.4f point=%.8f tick_size=%.8f tick_loss_value=%.8f stops_level=%d",
      contract,minimum,maximum,step,_Point,tickSize,tickLossValue,(int)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL));
   PrintFormat("V25_PROBE quote_bid=%.5f quote_ask=%.5f closed_M1_ATR14=%.5f stop_distance=%.5f min_loss_ok=%d min_loss=%.2f min_margin_ok=%d min_margin=%.2f",
      tick.bid,tick.ask,values[0],distance,minLossOk,minLoss,minMarginOk,minMargin);
   PrintFormat("V25_PROBE candidate_lots=%.4f volume_valid=%d loss_ok=%d loss=%.2f margin_ok=%d margin=%.2f max_risk_at_current_equity_3pct=%.2f",
      InpCandidateLots,validCandidate,candidateLossOk,candidateLoss,candidateMarginOk,candidateMargin,
      AccountInfoDouble(ACCOUNT_EQUITY)*0.03);
}
