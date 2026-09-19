#include "../Include/QuantumTitan/V20Signal.mqh"

int V20TestCount=0;
bool V20Check(bool condition,string name)
{
   ++V20TestCount; if(!condition) Print("V20_TEST_FAIL: ",name); return condition;
}

bool V20RunSignalTests()
{
   bool ok=true; string reason; V20Frame f={};
   f.close1=103.0; f.high1=103.5; f.low1=101.5; f.high2=102.0; f.low2=100.5;
   f.high3=101.5; f.low3=99.5; f.high4=101.0; f.low4=100.0; f.atr=1.0;
   ok=V20Check(V20Signal(f,reason)==-1 && reason=="UPPER_BREAKOUT_EXHAUSTION_SELL","upper breakout fades short") && ok;
   f.close1=102.0; ok=V20Check(V20Signal(f,reason)==0,"upper equality has no signal") && ok;
   f.close1=97.0; f.high1=98.5; f.low1=96.5; f.high2=100.5; f.low2=98.0;
   f.high3=100.0; f.low3=98.5; f.high4=99.5; f.low4=99.0;
   ok=V20Check(V20Signal(f,reason)==1 && reason=="LOWER_BREAKOUT_EXHAUSTION_BUY","lower breakout fades long") && ok;
   f.close1=98.0; ok=V20Check(V20Signal(f,reason)==0,"lower equality has no signal") && ok;
   f.close1=97.0; f.atr=0.0; ok=V20Check(V20Signal(f,reason)==0 && reason=="INVALID_DATA","invalid ATR rejected") && ok;
   f.atr=1.0; f.high2=97.0; f.low2=98.0; ok=V20Check(V20Signal(f,reason)==0 && reason=="INVALID_DATA","invalid bar rejected") && ok;
   ok=V20Check(MathAbs(V20Round(100.21,0.10,true)-100.30)<1e-8,"outward round up") && ok;
   ok=V20Check(MathAbs(V20Round(100.29,0.10,false)-100.20)<1e-8,"outward round down") && ok;
   ok=V20Check(V20Round(100.25,0.0,true)==0.0,"invalid tick rejected") && ok;
   ok=V20Check(V20SignalAlive(10,10) && !V20SignalAlive(11,10),"ten second expiry boundary") && ok;
   ok=V20Check(V20InEntryWindow(1,56,18,2,1,57) && !V20InEntryWindow(1,57,18,2,1,57),"01:57 entry cutoff") && ok;
   ok=V20Check(V20InEntryWindow(18,0,18,2,1,57) && !V20InEntryWindow(2,0,18,2,1,57) && !V20InEntryWindow(17,59,18,2,1,57),"overnight session bounds") && ok;
   ok=V20Check(V20OrderCheckAccepted(0) && !V20OrderCheckAccepted(TRADE_RETCODE_DONE),"OrderCheck code zero predicate") && ok;
   PrintFormat("V20_SELF_TESTS: %s checks=%d",ok ? "PASS" : "FAIL",V20TestCount); return ok;
}
