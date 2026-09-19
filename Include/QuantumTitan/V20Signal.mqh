#ifndef QT_V20_SIGNAL_MQH
#define QT_V20_SIGNAL_MQH

struct V20Frame
{
   double close1,high1,low1;
   double high2,low2,high3,low3,high4,low4;
   double atr;
};

bool V20ValidNumber(double value) { return MathIsValidNumber(value) && value!=EMPTY_VALUE; }
bool V20SignalAlive(long age,int expirySeconds) { return age>=0 && age<=expirySeconds; }

bool V20InEntryWindow(int hour,int minute,int startHour,int endHour,int cutoffHour,int cutoffMinute)
{
   if(hour<0 || hour>23 || minute<0 || minute>59 || startHour<0 || startHour>23 || endHour<0 || endHour>23) return false;
   bool inSession=startHour<endHour ? hour>=startHour && hour<endHour : (startHour>endHour ? hour>=startHour || hour<endHour : true);
   return inSession && !(hour==cutoffHour && minute>=cutoffMinute);
}

bool V20OrderCheckAccepted(uint retcode) { return retcode==0; }

int V20Signal(const V20Frame &f,string &reason)
{
   reason="NO_BREAKOUT";
   if(!V20ValidNumber(f.close1) || !V20ValidNumber(f.high1) || !V20ValidNumber(f.low1) ||
      !V20ValidNumber(f.high2) || !V20ValidNumber(f.low2) || !V20ValidNumber(f.high3) ||
      !V20ValidNumber(f.low3) || !V20ValidNumber(f.high4) || !V20ValidNumber(f.low4) ||
      !V20ValidNumber(f.atr) || f.atr<=0.0 || f.high1<f.low1 || f.high2<f.low2 ||
      f.high3<f.low3 || f.high4<f.low4 || f.close1>f.high1 || f.close1<f.low1)
   { reason="INVALID_DATA"; return 0; }
   double priorHigh=MathMax(f.high2,MathMax(f.high3,f.high4));
   double priorLow=MathMin(f.low2,MathMin(f.low3,f.low4));
   if(f.close1>priorHigh) { reason="UPPER_BREAKOUT_EXHAUSTION_SELL"; return -1; }
   if(f.close1<priorLow) { reason="LOWER_BREAKOUT_EXHAUSTION_BUY"; return 1; }
   return 0;
}

double V20Round(double price,double tick,bool upward)
{
   if(!V20ValidNumber(price) || !V20ValidNumber(tick) || price<=0.0 || tick<=0.0) return 0.0;
   return (upward ? MathCeil(price/tick-1e-9) : MathFloor(price/tick+1e-9))*tick;
}

#endif
