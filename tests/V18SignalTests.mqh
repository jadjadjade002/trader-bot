#include "../Include/QuantumTitan/V18Signal.mqh"
int V18TestCount=0;
bool V18Check(bool ok,string name)
{
   ++V18TestCount;
   if(!ok) Print("V18_TEST_FAIL: ",name);
   return ok;
}
bool V18RunSignalTests()
{
   bool ok=true; string reason; V18Frame f={};
   f.open=99.2; f.high=99.8; f.low=98.5; f.close=99.6; f.atr=1.0;
   f.rsi=46; f.prevRsi=42; f.htfFast=100.2; f.htfSlow=100.0; f.adx=24;
   f.swingLow=99.0; f.swingHigh=101.0;
   ok=V18Check(V18Signal(f,reason)==1,"buy reclaim") && ok;
   f.adx=40; ok=V18Check(V18Signal(f,reason)==1,"buy accepts ADX 40") && ok; f.adx=24;
   f.open=100.8; f.high=101.5; f.low=100.2; f.close=100.4;
   f.rsi=54; f.prevRsi=58; f.htfFast=99.8; f.htfSlow=100.0;
   ok=V18Check(V18Signal(f,reason)==-1,"sell reclaim") && ok;
   f.high=102.5; ok=V18Check(V18Signal(f,reason)==0,"shock bar rejected") && ok; f.high=101.5;
   f.htfFast=101; ok=V18Check(V18Signal(f,reason)==0,"HTF disagreement") && ok;
   f.htfFast=100.2; f.rsi=0; ok=V18Check(V18Signal(f,reason)==0,"invalid momentum") && ok;
   ok=V18Check(V18Round(100.25,0.0,true)==0.0,"invalid tick rejected") && ok;
   PrintFormat("V18_SELF_TESTS: %s checks=%d",ok ? "PASS" : "FAIL",V18TestCount);
   return ok;
}
