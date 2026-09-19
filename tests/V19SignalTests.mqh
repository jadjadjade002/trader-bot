#include "../Include/QuantumTitan/V19Signal.mqh"

int V19TestCount=0;
bool V19Check(bool condition,string name)
{
   ++V19TestCount;
   if(!condition) Print("V19_TEST_FAIL: ",name);
   return condition;
}

bool V19RunSignalTests()
{
   bool ok=true; string reason; V19Frame f={};
   f.close1=103.0; f.high1=103.5; f.low1=101.5; f.high2=102.0; f.low2=100.5;
   f.high3=101.5; f.low3=99.5; f.high4=101.0; f.low4=100.0; f.atr=1.0;
   ok=V19Check(V19Signal(f,reason)==1,"strict buy breakout") && ok;
   f.close1=102.0; ok=V19Check(V19Signal(f,reason)==0,"equality is not a buy breakout") && ok;
   f.close1=97.0; f.high1=98.5; f.low1=96.5; f.high2=100.5; f.low2=98.0;
   f.high3=100.0; f.low3=98.5; f.high4=99.5; f.low4=99.0;
   ok=V19Check(V19Signal(f,reason)==-1,"mirrored strict sell breakout") && ok;
   f.close1=98.0; ok=V19Check(V19Signal(f,reason)==0,"equality is not a sell breakout") && ok;
   f.close1=97.0; f.atr=0.0; ok=V19Check(V19Signal(f,reason)==0 && reason=="INVALID_DATA","invalid ATR rejected") && ok;
   f.atr=1.0; f.high2=97.0; f.low2=98.0; ok=V19Check(V19Signal(f,reason)==0 && reason=="INVALID_DATA","invalid bar rejected") && ok;
   ok=V19Check(MathAbs(V19Round(100.21,0.10,true)-100.30)<1e-8,"outward round up") && ok;
   ok=V19Check(MathAbs(V19Round(100.29,0.10,false)-100.20)<1e-8,"outward round down") && ok;
   ok=V19Check(V19Round(100.25,0.0,true)==0.0,"invalid tick rejected") && ok;
   ok=V19Check(V19SignalAlive(10,10) && !V19SignalAlive(11,10),"ten second expiry boundary") && ok;
   ok=V19Check(V19InEntryWindow(1,56,18,2,1,57) && !V19InEntryWindow(1,57,18,2,1,57),"01:57 entry cutoff") && ok;
   ok=V19Check(V19InEntryWindow(18,0,18,2,1,57) && !V19InEntryWindow(2,0,18,2,1,57) && !V19InEntryWindow(17,59,18,2,1,57),"overnight session bounds") && ok;
   ok=V19Check(V19OrderCheckAccepted(0) && !V19OrderCheckAccepted(TRADE_RETCODE_DONE),"OrderCheck code zero predicate") && ok;
   PrintFormat("V19_SELF_TESTS: %s checks=%d",ok ? "PASS" : "FAIL",V19TestCount);
   return ok;
}
