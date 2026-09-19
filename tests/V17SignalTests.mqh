#include "../Include/QuantumTitan/V17Signal.mqh"
int V17TestCount=0;
bool V17Check(bool ok,string name)
{
   ++V17TestCount;
   if(!ok) Print("V17_TEST_FAIL: ",name);
   return ok;
}
bool V17RunSignalTests()
{
   bool ok=true; string reason;
   V17Frame f={};
   f.open=99.8; f.high=100.5; f.low=99.6; f.close=100.4;
   f.fast=100; f.prevFast=99.9; f.slow=99; f.atr=1;
   f.rsi=55; f.prevRsi=52; f.htfFast=100; f.htfPrevFast=99.8; f.htfSlow=99; f.adx=25;
   ok=V17Check(V17Signal(f,reason)==1,"trend buy") && ok;
   f.htfFast=98; ok=V17Check(V17Signal(f,reason)==0,"M5 disagreement") && ok; f.htfFast=100;
   f.close=101; ok=V17Check(V17Signal(f,reason)==0,"extended entry") && ok; f.close=100.4;
   f.atr=0; ok=V17Check(V17Signal(f,reason)==0,"invalid ATR") && ok; f.atr=1;
   f.high=103; ok=V17Check(V17Signal(f,reason)==0,"shock candle") && ok; f.high=100.5;
   f.adx=20; ok=V17Check(V17Signal(f,reason)==0,"transition regime") && ok;
   f.open=100.2; f.high=100.4; f.low=99.5; f.close=99.6;
   f.prevFast=100.1; f.slow=101; f.rsi=45; f.prevRsi=48;
   f.htfPrevFast=100.2; f.htfSlow=101; f.adx=25;
   ok=V17Check(V17Signal(f,reason)==-1,"trend sell") && ok;
   f.high=102; f.low=101; f.open=101.8; f.close=101.2;
   ok=V17Check(V17Signal(f,reason)==0,"one-sided touch is not retest") && ok;
   f.open=99.2; f.high=99.7; f.low=98.7; f.close=99.5; f.atr=1;
   f.lower=99; f.upper=101; f.middle=100; f.htfFast=100; f.htfSlow=100.2;
   f.adx=15; f.rsi=40; f.prevRsi=35;
   ok=V17Check(V17Signal(f,reason)==1,"range buy rejection") && ok;
   f.open=100.8; f.high=101.3; f.low=100.3; f.close=100.5;
   f.rsi=60; f.prevRsi=65;
   ok=V17Check(V17Signal(f,reason)==-1,"range sell rejection") && ok;
   ok=V17Check(V17Signal(f,reason,1)==0,"trend-only rejects range") && ok;
   f.swingHigh=101; f.swingLow=99;
   ok=V17Check(V17Signal(f,reason,3)==-1,"sweep sell reclaim") && ok;
   f.open=99.2; f.high=99.7; f.low=98.7; f.close=99.5;
   f.rsi=40; f.prevRsi=35;
   ok=V17Check(V17Signal(f,reason,3)==1,"sweep buy reclaim") && ok;
   f.adx=30; f.htfFast=99; f.htfPrevFast=100;
   ok=V17Check(V17Signal(f,reason,3)==0,"sweep against strong M5 rejected") && ok;
   ok=V17Check(V17Session(23,18,2) && V17Session(1,18,2) && !V17Session(2,18,2),"midnight session") && ok;
   ok=V17Check(V17Session(8,8,16) && !V17Session(16,8,16),"normal session") && ok;
   ok=V17Check(V17Session(12,0,0),"24h session") && ok;
   double stop=0;
   ok=V17Check(V17SelectStopDistance(V17_STOP_FIXED,1.8,1.4,2.1,3.5,stop) && MathAbs(stop-1.8)<1e-8,"fixed stop selection") && ok;
   ok=V17Check(V17SelectStopDistance(V17_STOP_STRUCTURAL,1.8,1.4,2.1,3.5,stop) && MathAbs(stop-2.1)<1e-8,"structural stop selection") && ok;
   ok=V17Check(V17SelectStopDistance(V17_STOP_STRUCTURAL,0,1.4,2.1,3.5,stop) && MathAbs(stop-2.1)<1e-8,"structural stop needs no fixed value") && ok;
   ok=V17Check(V17SelectStopDistance(V17_STOP_HYBRID,1.8,1.4,2.1,3.5,stop) && MathAbs(stop-2.1)<1e-8,"hybrid stop selection") && ok;
   ok=V17Check(!V17SelectStopDistance(V17_STOP_HYBRID,1.8,1.4,4.0,3.5,stop),"oversized structural stop rejected") && ok;
   ok=V17Check(MathAbs(V17Round(100.13,0.25,true)-100.25)<1e-8,"round up tick") && ok;
   ok=V17Check(MathAbs(V17Round(100.13,0.25,false)-100)<1e-8,"round down tick") && ok;
   PrintFormat("V17_SELF_TESTS: %s checks=%d",ok ? "PASS" : "FAIL",V17TestCount);
   return ok;
}
