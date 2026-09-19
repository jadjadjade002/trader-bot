#ifndef QT_V18_SIGNAL_MQH
#define QT_V18_SIGNAL_MQH

struct V18Frame
{
   double open,high,low,close,prevClose;
   double atr,rsi,prevRsi;
   double fast,slow;
   double htfFast,htfSlow,adx;
   double swingHigh,swingLow;
};

// One bounded hypothesis: a completed-bar liquidity sweep must reclaim the
// prior range and agree with momentum. This module contains no trade state.
int V18Signal(const V18Frame &f,string &reason)
{
   reason="NO_SETUP";
   double range=f.high-f.low;
   if(f.atr<=0 || range<=0 || !MathIsValidNumber(f.atr)) { reason="INVALID_DATA"; return 0; }
   if(range>1.8*f.atr) { reason="SHOCK_BAR"; return 0; }
   double lower=(MathMin(f.open,f.close)-f.low)/range;
   double upper=(f.high-MathMax(f.open,f.close))/range;
   double body=MathAbs(f.close-f.open)/range;
   if(f.low<f.swingLow && f.close>f.swingLow && f.close>f.open &&
      lower>=0.40 && body>=0.15 && f.rsi>f.prevRsi && f.rsi<=52.0 &&
      f.htfFast>=f.htfSlow)
   { reason="SWEEP_RECLAIM_BUY"; return 1; }
   if(f.high>f.swingHigh && f.close<f.swingHigh && f.close<f.open &&
      upper>=0.40 && body>=0.15 && f.rsi<f.prevRsi && f.rsi>=48.0 &&
      f.htfFast<=f.htfSlow)
   { reason="SWEEP_RECLAIM_SELL"; return -1; }
   return 0;
}

double V18Round(double price,double tick,bool upward)
{
   if(!MathIsValidNumber(price) || !MathIsValidNumber(tick) || tick<=0.0) return 0.0;
   return (upward ? MathCeil(price/tick-1e-9) : MathFloor(price/tick+1e-9))*tick;
}

#endif
