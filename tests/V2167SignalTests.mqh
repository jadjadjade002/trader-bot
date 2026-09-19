#ifndef QT_V2167_SIGNAL_TESTS_MQH
#define QT_V2167_SIGNAL_TESTS_MQH
#include "../Include/QuantumTitan/V2167Signal.mqh"

int V2167TestCount=0;
bool V2167Check(bool condition,string name)
{
   ++V2167TestCount;
   if(!condition) Print("V2167_TEST_FAIL: ",name);
   return condition;
}

void V2167TestBars(MqlRates &bars[],int power,bool falling=false)
{
   ArrayResize(bars,40);
   ArraySetAsSeries(bars,false); // Explicit assignment makes index 0 newest.
   for(int i=0;i<40;++i)
   {
      double t=40-i;
      double move=(power==3 ? t*t*t : t*t);
      double price=100000+(falling ? -move : move);
      ZeroMemory(bars[i]);
      bars[i].time=(datetime)(1800000000-i*60);
      bars[i].open=price; bars[i].close=price;
      bars[i].high=price+1; bars[i].low=price-1;
   }
}

bool V2167RunSignalTests()
{
   V2167TestCount=0;
   bool ok=true; string reason;
   V2167Frame f={};
   f.open=100; f.high=102; f.low=99; f.close=101;
   f.fast=100; f.slow=98; f.rsi=55; f.momentum=0; f.point=0.01;
   ok=V2167Check(V2167Signal(f,reason)==1,"long") && ok;
   f.rsi=40; ok=V2167Check(V2167Signal(f,reason)==1,"long RSI lower inclusive") && ok;
   f.rsi=70; ok=V2167Check(V2167Signal(f,reason)==1,"long RSI upper inclusive") && ok;
   f.rsi=70.01; ok=V2167Check(V2167Signal(f,reason)==0,"long RSI outside") && ok;
   f.rsi=55; f.momentum=-0.05;
   ok=V2167Check(V2167Signal(f,reason)==0,"long momentum boundary strict") && ok;
   f.momentum=-0.049;
   ok=V2167Check(V2167Signal(f,reason)==1,"long momentum inside") && ok;
   f.momentum=0; f.slow=f.fast;
   ok=V2167Check(V2167Signal(f,reason)==0,"equal EMAs reject") && ok;
   f.slow=f.close;
   ok=V2167Check(V2167Signal(f,reason)==0,"close at slow EMA rejects") && ok;
   f.slow=98; f.open=100.25; f.close=100.25; f.high=101; f.low=100;
   ok=V2167Check(V2167Signal(f,reason)==1,"exact 25 percent wick") && ok;
   f.open=100.24; f.close=100.24;
   ok=V2167Check(V2167Signal(f,reason)==0,"small wick doji rejects") && ok;
   f.open=101; f.close=102; f.high=103; f.low=f.fast+15*f.point;
   ok=V2167Check(V2167Signal(f,reason)==1,"touch tolerance inclusive") && ok;
   f.low+=0.001;
   ok=V2167Check(V2167Signal(f,reason)==0,"outside touch tolerance") && ok;

   f.open=101; f.high=102; f.low=99; f.close=100;
   f.fast=101; f.slow=103; f.rsi=45;
   ok=V2167Check(V2167Signal(f,reason)==-1,"short mirror") && ok;
   f.rsi=30; ok=V2167Check(V2167Signal(f,reason)==-1,"short RSI lower inclusive") && ok;
   f.rsi=60; ok=V2167Check(V2167Signal(f,reason)==-1,"short RSI upper inclusive") && ok;
   f.rsi=29.99; ok=V2167Check(V2167Signal(f,reason)==0,"short RSI outside") && ok;
   f.rsi=45; f.momentum=0.05;
   ok=V2167Check(V2167Signal(f,reason)==0,"short momentum boundary strict") && ok;
   f.momentum=0.049;
   ok=V2167Check(V2167Signal(f,reason)==-1,"short momentum inside") && ok;
   f.high=100;
   ok=V2167Check(V2167Signal(f,reason)==0 && reason=="INVALID_DATA","OHLC inconsistent") && ok;
   f.high=102; f.point=0;
   ok=V2167Check(V2167Signal(f,reason)==0 && reason=="INVALID_DATA","zero point") && ok;
   f.point=0.01; f.rsi=101;
   ok=V2167Check(V2167Signal(f,reason)==0 && reason=="INVALID_DATA","invalid RSI") && ok;
   f.rsi=45; f.momentum=EMPTY_VALUE;
   ok=V2167Check(V2167Signal(f,reason)==0 && reason=="INVALID_DATA","empty momentum") && ok;
   f.momentum=0; f.fast=EMPTY_VALUE;
   ok=V2167Check(V2167Signal(f,reason)==0 && reason=="INVALID_DATA","empty EMA") && ok;

   MqlRates bars[]; double current=0,previous=0;
   V2167TestBars(bars,2);
   // For close=t^2, symmetric +/-1 high/low: delta(t)=19*t-152.
   ok=V2167Check(V2167Momentum(bars,current,previous) &&
      MathAbs(current-19)<1e-8 && MathAbs(previous-19)<1e-8,"quadratic rolling-basis slope") && ok;
   V2167TestBars(bars,3);
   // For close=t^3: delta=28.5*t^2-456*t+2617.25.
   // Slope on t=21..40 is 1282.5; on t=20..39 it is 1225.5.
   ok=V2167Check(V2167Momentum(bars,current,previous) &&
      MathAbs(current-1282.5)<1e-8 && MathAbs(previous-1225.5)<1e-8,"cubic current and prior slopes") && ok;
   bars[39].close+=0.5;
   ok=V2167Check(V2167Momentum(bars,current,previous) &&
      MathAbs(current-1282.5)<1e-8 && MathAbs(previous-1225.5)>1e-8,"oldest bar affects prior only") && ok;
   V2167TestBars(bars,3,true);
   ok=V2167Check(V2167Momentum(bars,current,previous) &&
      MathAbs(current+1282.5)<1e-8 && MathAbs(previous+1225.5)<1e-8,"falling chronological sign") && ok;
   bars[20].time-=60;
   ok=V2167Check(!V2167Momentum(bars,current,previous),"missing or duplicate minute rejects") && ok;
   V2167TestBars(bars,2); bars[10].high=bars[10].low-1;
   ok=V2167Check(!V2167Momentum(bars,current,previous),"invalid series OHLC") && ok;
   V2167TestBars(bars,2); bars[0].close=EMPTY_VALUE;
   ok=V2167Check(!V2167Momentum(bars,current,previous),"empty series value") && ok;
   V2167TestBars(bars,2); ArrayResize(bars,39);
   current=99; previous=99;
   ok=V2167Check(!V2167Momentum(bars,current,previous) && current==0 && previous==0,"insufficient bars clears outputs") && ok;

   ok=V2167Check(V2167EntryMinute(18,0) && V2167EntryMinute(23,59) &&
      V2167EntryMinute(0,0) && V2167EntryMinute(1,49),"entry session inclusive") && ok;
   ok=V2167Check(!V2167EntryMinute(17,59) && !V2167EntryMinute(1,50) &&
      !V2167EntryMinute(2,0) && !V2167EntryMinute(24,0) && !V2167EntryMinute(18,60),"session boundaries and invalid clock") && ok;
   ok=V2167Check(V2167SignalAlive(0) && V2167SignalAlive(10) &&
      !V2167SignalAlive(-1) && !V2167SignalAlive(11),"signal age inclusive 0..10") && ok;
   ok=V2167Check(MathAbs(V2167Round(100.13,0.25,true)-100.25)<1e-8 &&
      MathAbs(V2167Round(100.13,0.25,false)-100)<1e-8,"tick rounding directions") && ok;
   ok=V2167Check(MathAbs(V2167Round(100.25,0.25,true)-100.25)<1e-8 &&
      MathAbs(V2167Round(100.25,0.25,false)-100.25)<1e-8 &&
      V2167Round(100,0,true)==0,"exact tick and invalid step") && ok;
   PrintFormat("V2167_SELF_TESTS: %s checks=%d",ok ? "PASS" : "FAIL",V2167TestCount);
   return ok;
}
#endif
