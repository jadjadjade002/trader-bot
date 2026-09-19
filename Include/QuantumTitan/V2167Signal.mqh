#ifndef QT_V2167_SIGNAL_MQH
#define QT_V2167_SIGNAL_MQH

struct V2167Frame
{
   double open,high,low,close,fast,slow,rsi,momentum,point;
};

bool V2167Positive(double value)
{
   return MathIsValidNumber(value) && value!=EMPTY_VALUE && value>0;
}

bool V2167OHLC(double open,double high,double low,double close)
{
   return V2167Positive(open) && V2167Positive(high) &&
          V2167Positive(low) && V2167Positive(close) &&
          high>=low && high>=MathMax(open,close) && low<=MathMin(open,close);
}

int V2167Signal(const V2167Frame &f,string &reason)
{
   reason="INVALID_DATA";
   if(!V2167OHLC(f.open,f.high,f.low,f.close) || f.high<=f.low ||
      !V2167Positive(f.fast) || !V2167Positive(f.slow) || !V2167Positive(f.point) ||
      !MathIsValidNumber(f.rsi) || f.rsi<0 || f.rsi>100 ||
      !MathIsValidNumber(f.momentum) || f.momentum==EMPTY_VALUE) return 0;
   reason="NO_SETUP";
   double range=f.high-f.low;
   double lower=(MathMin(f.open,f.close)-f.low)/range;
   double upper=(f.high-MathMax(f.open,f.close))/range;
   if(f.fast>f.slow && f.close>f.slow && f.low<=f.fast+15*f.point &&
      (lower>=0.25 || f.close>f.open) && f.momentum> -0.05 && f.rsi>=40 && f.rsi<=70)
   { reason="VELOCITY_BUY"; return 1; }
   if(f.fast<f.slow && f.close<f.slow && f.high>=f.fast-15*f.point &&
      (upper>=0.25 || f.close<f.open) && f.momentum<0.05 && f.rsi>=30 && f.rsi<=60)
   { reason="VELOCITY_SELL"; return -1; }
   return 0;
}

// Newest-first deltas; x increases from oldest to newest.
double V2167Slope(const double &delta[],int offset)
{
   double numerator=0;
   for(int i=0;i<20;++i) numerator+=(i-9.5)*delta[offset+19-i];
   return numerator/665.0; // sum((i-9.5)^2), i=0..19
}

// Caller supplies completed M1 bars, bars[0] newest. No forming-bar reads here.
// This is a rolling-basis regression SLOPE, not LazyBear's regression endpoint.
bool V2167Momentum(const MqlRates &bars[],double &current,double &previous)
{
   current=0; previous=0;
   if(ArraySize(bars)<40) return false;
   for(int i=0;i<40;++i)
   {
      if(bars[i].time<=0 || !V2167OHLC(bars[i].open,bars[i].high,bars[i].low,bars[i].close))
         return false;
      if(i>0 && bars[i-1].time-bars[i].time!=60) return false;
   }
   double delta[21];
   for(int k=0;k<=20;++k)
   {
      double highest=bars[k].high,lowest=bars[k].low,sum=0;
      for(int j=0;j<20;++j)
      {
         highest=MathMax(highest,bars[k+j].high);
         lowest=MathMin(lowest,bars[k+j].low);
         sum+=bars[k+j].close;
      }
      double donchian=(highest+lowest)/2.0;
      delta[k]=bars[k].close-(donchian+sum/20.0)/2.0;
      if(!MathIsValidNumber(delta[k]) || delta[k]==EMPTY_VALUE) return false;
   }
   current=V2167Slope(delta,0); previous=V2167Slope(delta,1);
   if(!MathIsValidNumber(current) || !MathIsValidNumber(previous))
   { current=0; previous=0; return false; }
   return true;
}

bool V2167EntryMinute(int hour,int minute)
{
   if(hour<0 || hour>23 || minute<0 || minute>59) return false;
   return hour>=18 || hour==0 || (hour==1 && minute<=49);
}

bool V2167SignalAlive(long age)
{
   return age>=0 && age<=10;
}

double V2167Round(double price,double step,bool up)
{
   if(!V2167Positive(price) || !V2167Positive(step)) return 0;
   return (up ? MathCeil(price/step-1e-9) : MathFloor(price/step+1e-9))*step;
}

#endif
