#ifndef QT_V17_SIGNAL_MQH
#define QT_V17_SIGNAL_MQH

// All fields represent completed bars. No order, account or terminal state here.
struct V17Frame
{
   double open, high, low, close, prevClose;
   double fast, prevFast, slow, atr, rsi, prevRsi;
   double htfFast, htfPrevFast, htfSlow, adx;
   double upper, lower, middle;
   double swingHigh,swingLow;
};

// The stop rule is explicit so a visible input cannot silently be overridden.
enum ENUM_V17_STOP_MODE
{
   V17_STOP_FIXED=0,
   V17_STOP_STRUCTURAL=1,
   V17_STOP_HYBRID=2
};

// Select the intended stop distance. Oversized setups are rejected by returning false;
// they are never silently clipped inside the rejection candle.
bool V17SelectStopDistance(ENUM_V17_STOP_MODE mode,double fixedDistance,
                           double atrDistance,double structuralDistance,
                           double maximumDistance,double &distance)
{
   if(atrDistance<=0 || structuralDistance<=0 || maximumDistance<=0)
      return false;
   if(mode==V17_STOP_FIXED)
   {
      if(fixedDistance<=0) return false;
      distance=fixedDistance;
   }
   else if(mode==V17_STOP_STRUCTURAL) distance=MathMax(atrDistance,structuralDistance);
   else
   {
      if(fixedDistance<=0) return false;
      distance=MathMax(fixedDistance,structuralDistance);
   }
   return distance<=maximumDistance;
}

int V17Signal(const V17Frame &f, string &reason, int mode=0)
{
   reason="NO_SETUP";
   double range=f.high-f.low;
   if(f.atr<=0 || range<=0 || !MathIsValidNumber(f.atr))
   { reason="INVALID_DATA"; return 0; }
   if(range>2.0*f.atr) { reason="EXTENDED_CANDLE"; return 0; }
   double body=MathAbs(f.close-f.open)/range;
   double lowerWick=(MathMin(f.open,f.close)-f.low)/range;
   double upperWick=(f.high-MathMax(f.open,f.close))/range;
   double tolerance=0.20*f.atr;
   // Require actual overlap with the EMA area AND a close back through it.
   bool touch=f.low<=f.fast+tolerance && f.high>=f.fast-tolerance;
   bool near=MathAbs(f.close-f.fast)<=0.65*f.atr;
   if(mode==3)
   {
      if(f.low<f.swingLow && f.close>f.swingLow && lowerWick>=0.35 &&
         f.close>f.open && f.rsi>f.prevRsi && f.rsi<55 &&
         (f.htfFast>=f.htfPrevFast || f.adx<22))
      { reason="SWEEP_RECLAIM_BUY"; return 1; }
      if(f.high>f.swingHigh && f.close<f.swingHigh && upperWick>=0.35 &&
         f.close<f.open && f.rsi<f.prevRsi && f.rsi>45 &&
         (f.htfFast<=f.htfPrevFast || f.adx<22))
      { reason="SWEEP_RECLAIM_SELL"; return -1; }
      return 0;
   }
   if(mode!=2 && f.adx>=22.0)
   {
      if(f.htfFast>f.htfSlow && f.htfFast>f.htfPrevFast &&
         f.fast>f.slow && f.fast>f.prevFast && touch && near &&
         f.close>f.fast && f.close>f.open && body>=0.25 &&
         f.rsi>=45 && f.rsi<=65 && f.rsi>f.prevRsi)
      { reason="TREND_PULLBACK_BUY"; return 1; }
      if(f.htfFast<f.htfSlow && f.htfFast<f.htfPrevFast &&
         f.fast<f.slow && f.fast<f.prevFast && touch && near &&
         f.close<f.fast && f.close<f.open && body>=0.25 &&
         f.rsi>=35 && f.rsi<=55 && f.rsi<f.prevRsi)
      { reason="TREND_PULLBACK_SELL"; return -1; }
   }
   // Range fades only when M5 is flat. ADX 18..22 is a transition: skip.
   else if(mode!=1 && f.adx<=18.0 && MathAbs(f.htfFast-f.htfSlow)<=0.8*f.atr)
   {
      if(f.low<f.lower && f.close>f.lower && f.close<f.middle &&
         f.close>f.open && lowerWick>=0.35 && f.rsi<45 && f.rsi>f.prevRsi)
      { reason="RANGE_REJECTION_BUY"; return 1; }
      if(f.high>f.upper && f.close<f.upper && f.close>f.middle &&
         f.close<f.open && upperWick>=0.35 && f.rsi>55 && f.rsi<f.prevRsi)
      { reason="RANGE_REJECTION_SELL"; return -1; }
   }

   // Mode 0: Also capture high-conviction sweeps in trending or ranging environments
   if(mode==0 && (f.adx>=22.0 || f.adx<=18.0) && f.swingHigh>0 && f.swingLow>0)
   {
      if(f.low<f.swingLow && f.close>f.swingLow && lowerWick>=0.35 &&
         f.close>f.open && f.rsi>f.prevRsi && f.rsi<58 &&
         (f.htfFast>=f.htfPrevFast || f.adx<22))
      { reason="SWEEP_RECLAIM_BUY"; return 1; }
      if(f.high>f.swingHigh && f.close<f.swingHigh && upperWick>=0.35 &&
         f.close<f.open && f.rsi<f.prevRsi && f.rsi>42 &&
         (f.htfFast<=f.htfPrevFast || f.adx<22))
      { reason="SWEEP_RECLAIM_SELL"; return -1; }
   }
   return 0;
}

bool V17Session(int hour,int start,int end)
{
   if(start==end) return true;
   return start<end ? hour>=start && hour<end : hour>=start || hour<end;
}

// Broker price increments may differ from _Point; direction is explicit.
double V17Round(double price,double tick,bool upward)
{
   return (upward ? MathCeil(price/tick-1e-9) : MathFloor(price/tick+1e-9))*tick;
}

#endif
