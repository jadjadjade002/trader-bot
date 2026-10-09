// Actual compiled MQL fixture assertions. Not market data/profit evidence.
int r3FixtureChecks=0;
bool R3Assert(bool condition,string name)
{
   r3FixtureChecks++;
   if(!condition) Print("R3_NATIVE_FIXTURE_FAIL ",name);
   return condition;
}
void R3FixtureBar(MqlRates &r,double o,double h,double l,double c,datetime t)
{
   ZeroMemory(r);r.open=o;r.high=h;r.low=l;r.close=c;r.time=t;r.tick_volume=100;
}
void R3Reflect(const MqlRates &src[],MqlRates &dst[])
{
   ArrayResize(dst,ArraySize(src));
   for(int i=0;i<ArraySize(src);i++)
      R3FixtureBar(dst[i],200-src[i].open,200-src[i].low,200-src[i].high,200-src[i].close,src[i].time);
}
bool RunR3FixtureTests()
{
   bool ok=true;r3FixtureChecks=0;
   MqlRates m1[],m5[],mirror1[],mirror5[];ArrayResize(m1,23);ArrayResize(m5,13);
   double atr[23],e20[6]={100.1,100.05,99.8,99.6,99.3,99.05},mirror20[6];
   double e9[2]={101,101},mirror9[2]={99,99};
   datetime t=2000000000;
   for(int i=0;i<23;i++){atr[i]=1;R3FixtureBar(m1[i],100,101,99,100,t-i*60);}
   for(int i=0;i<13;i++)R3FixtureBar(m5[i],100-i*0.2,100.2-i*0.2,99.8-i*0.2,100-i*0.2,t-i*300);
   for(int i=0;i<6;i++)mirror20[i]=200-e20[i];
   ok=R3Assert(R3Trend(e20,99,1)==1,"trend_buy") && ok;
   ok=R3Assert(R3Trend(mirror20,101,1)==-1,"trend_sell_mirror") && ok;
   ok=R3Assert(R3Trend(e20,99,0)==0,"invalid_trend_atr") && ok;
   R3FixtureBar(m1[1],101.8,102.2,101.7,102,t-60);
   R3FixtureBar(m1[0],102.1,102.3,100.7,100.8,t);
   ok=R3Assert(R3Blowoff(InpEntryStrength,m1,atr,e20,99,1,e9)==-1,"A_fade_sell") && ok;
   R3Reflect(m1,mirror1);
   ok=R3Assert(R3Blowoff(InpEntryStrength,mirror1,atr,mirror20,101,1,mirror9)==1,"A_fade_buy_mirror") && ok;
   double fastSlope[6]={100.3,100.05,99.8,99.6,99.3,99.05};
   ok=R3Assert(R3Blowoff(InpEntryStrength,m1,atr,fastSlope,99,1,e9)==0,"A_accelerating_trend_rejected") && ok;
   for(int i=0;i<23;i++)R3FixtureBar(m1[i],101,103,99,101,t-i*60);
   R3FixtureBar(m1[0],102.55,102.9,102.4,102.5,t);
   double flat[6]={100,100,100,100,100,100};
   ok=R3Assert(R3Range(InpEntryStrength,m1,atr,flat,100,1)==-1,"B_internal_sell") && ok;
   R3Reflect(m1,mirror1);
   ok=R3Assert(R3Range(InpEntryStrength,mirror1,atr,flat,100,1)==1,"B_internal_buy_mirror") && ok;
   m1[0].high=103;
   ok=R3Assert(R3Range(InpEntryStrength,m1,atr,flat,100,1)==0,"B_boundary_sweep_rejected") && ok;
   for(int i=0;i<23;i++)R3FixtureBar(m1[i],100,100.2,99.8,100,t-i*60);
   R3FixtureBar(m1[4],101.8,102.2,101.7,102,t-240);
   R3FixtureBar(m1[3],102,102,101.6,101.7,t-180);
   R3FixtureBar(m1[2],101.7,101.8,101.4,101.5,t-120);
   R3FixtureBar(m1[1],101.5,101.7,101.3,101.4,t-60);
   R3FixtureBar(m1[0],101.5,102.2,101.3,102.1,t);
   e9[0]=101.7;mirror9[0]=98.3;
   ok=R3Assert(R3EfficientFlag(InpEntryStrength,m1,m5,atr,e20,99,1,e9)==1,"C_flag_buy") && ok;
   R3Reflect(m1,mirror1);R3Reflect(m5,mirror5);
   ok=R3Assert(R3EfficientFlag(InpEntryStrength,mirror1,mirror5,atr,mirror20,101,1,mirror9)==-1,"C_flag_sell_mirror") && ok;
   for(int i=0;i<13;i++)m5[i].close=100;
   ok=R3Assert(R3EfficientFlag(InpEntryStrength,m1,m5,atr,e20,99,1,e9)==0,"C_zero_path_rejected") && ok;
   ok=R3Assert(R3QuoteCost(100,100.08,100.04,1),"cost_allowed") && ok;
   ok=R3Assert(!R3QuoteCost(100,100.11,100.055,1),"spread_rejected") && ok;
   ok=R3Assert(!R3QuoteCost(100,100.08,99,1),"midpoint_chase_rejected") && ok;
   ok=R3Assert(!R3QuoteCost(100,100.08,100.04,0),"zero_atr_rejected") && ok;
   if(ok) Print("R3_NATIVE_FIXTURES_PASS checks=",r3FixtureChecks," preset=",InpEntryStrength);
   return ok;
}
