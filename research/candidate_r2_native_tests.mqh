// Actual MQL predicates inside isolated tester initialization. No profit claim.
int r2FixtureChecks=0;
bool R2Assert(bool condition,string name)
{
   r2FixtureChecks++;
   if(!condition) Print("R2_NATIVE_FIXTURE_FAIL ",name);
   return condition;
}
void R2FixtureBar(MqlRates &r,double o,double h,double l,double c,datetime t)
{
   ZeroMemory(r);r.open=o;r.high=h;r.low=l;r.close=c;r.time=t;r.tick_volume=100;
}
void R2Reflect(const MqlRates &src[],MqlRates &dst[])
{
   ArrayResize(dst,ArraySize(src));
   for(int i=0;i<ArraySize(src);i++)
      R2FixtureBar(dst[i],200-src[i].open,200-src[i].low,200-src[i].high,200-src[i].close,src[i].time);
}
bool RunR2FixtureTests()
{
   bool ok=true;r2FixtureChecks=0;ResetR2State();
   MqlRates r[],mirror[];ArrayResize(r,23);
   datetime t=2000000000;
   for(int i=0;i<23;i++) R2FixtureBar(r[i],100,102,99,100,t-i*60);
   R2FixtureBar(r[0],99.9,100.5,99.8,100.4,t);
   ok=R2Assert(R2Pullback(1,1,r[0],100.2,100)==1,"A_buy") && ok;
   R2Reflect(r,mirror);
   ok=R2Assert(R2Pullback(1,-1,mirror[0],99.8,100)==-1,"A_sell_mirror") && ok;
   R2FixtureBar(r[0],100.1,100.5,100.01,100.4,t);
   ok=R2Assert(R2Pullback(1,1,r[0],100.2,100)==0,"A_no_touch") && ok;
   double a2[3]={1,1,1};
   for(int i=1;i<4;i++) R2FixtureBar(r[i],100,100.3,99.7,100,t-i*60);
   R2FixtureBar(r[0],100,100.8,99.9,100.7,t);
   ok=R2Assert(R2Compression(1,1,r,100.2,a2)==1,"B_buy") && ok;
   R2Reflect(r,mirror);
   ok=R2Assert(R2Compression(1,-1,mirror,99.8,a2)==-1,"B_sell_mirror") && ok;
   r[2].high=101;
   ok=R2Assert(R2Compression(1,1,r,100.2,a2)==0,"B_not_compressed") && ok;
   for(int i=0;i<23;i++) R2FixtureBar(r[i],100,102,99,100,t-i*60);
   R2FixtureBar(r[1],99.2,100,98.8,99,t-60);
   R2FixtureBar(r[0],99,99.6,98.9,99.5,t);
   ok=R2Assert(R2RangeReversal(1,r,100,100,100,1)==1,"C_buy") && ok;
   R2Reflect(r,mirror);
   ok=R2Assert(R2RangeReversal(1,mirror,100,100,100,1)==-1,"C_sell_mirror") && ok;
   ok=R2Assert(R2RangeReversal(1,r,100,100,99,1)==0,"C_trend_not_range") && ok;
   for(int i=0;i<23;i++) R2FixtureBar(r[i],100,100.1,99,100,t-i*60);
   R2FixtureBar(r[1],98.2,98.5,97.8,98,t-60);
   R2FixtureBar(r[0],98,98.8,97.9,98.7,t);
   ok=R2Assert(R2Exhaustion(1,1,r,98.5,98.2)==1,"E_buy") && ok;
   R2Reflect(r,mirror);
   ok=R2Assert(R2Exhaustion(1,-1,mirror,101.5,101.8)==-1,"E_sell_mirror") && ok;
   ok=R2Assert(R2Exhaustion(1,1,r,97.5,98.2)==0,"E_chase_rejected") && ok;
   for(int i=0;i<23;i++) R2FixtureBar(r[i],99.5,100,99,99.5,t-i*60);
   R2FixtureBar(r[0],100.1,100.3,100.05,100.2,t);
   ok=R2Assert(R2BreakRetest(1,1,r,100.1)==0 && r2ArmedDirection==1,"D_arm_no_same_bar_entry") && ok;
   R2FixtureBar(r[0],100,100.3,99.95,100.2,t+60);
   R2AdvanceArm(1,100.1,99.9,1,r[0]);
   ok=R2Assert(R2BreakRetest(1,1,r,100.1)==1,"D_next_bar_retest") && ok;
   ok=R2Assert(R2BreakRetest(1,1,r,100.1)==0,"D_one_consumption") && ok;
   ResetR2State();r2ArmedDirection=1;r2ArmedLevel=100;r2ArmedOnBar=t;
   for(int k=1;k<=3;k++)
   {
      R2FixtureBar(r[0],100.4,100.6,100.3,100.5,t+k*60);
      R2AdvanceArm(1,100.4,100.2,1,r[0]);
      ok=R2Assert(r2ArmedDirection==1 && r2ArmedAge==k,"D_first_three_bars") && ok;
   }
   R2FixtureBar(r[0],100.4,100.6,100.3,100.5,t+240);
   R2AdvanceArm(1,100.4,100.2,1,r[0]);
   ok=R2Assert(r2ArmedDirection==0,"D_fourth_bar_expired") && ok;
   ResetR2State();r2ArmedDirection=1;r2ArmedLevel=100;r2ArmedOnBar=t;
   R2FixtureBar(r[0],100.4,100.6,100.3,100.5,t+60);
   R2AdvanceArm(0,100.4,100.2,1,r[0]);
   ok=R2Assert(r2ArmedDirection==0,"D_trend_loss_cancel") && ok;
   ResetR2State();r2ArmedDirection=1;r2ArmedLevel=100;r2ArmedOnBar=t;
   R2FixtureBar(r[0],99.7,99.9,99.6,99.8,t+60);
   R2AdvanceArm(1,100.1,99.9,1,r[0]);
   ok=R2Assert(r2ArmedDirection==0,"D_close_through_cancel") && ok;
   ok=R2Assert(R2QuoteCost(100,100.08,100.04,1),"cost_allowed") && ok;
   ok=R2Assert(!R2QuoteCost(100,100.11,100.055,1),"spread_rejected") && ok;
   ok=R2Assert(!R2QuoteCost(100,100.08,99,1),"midpoint_chase_rejected") && ok;
   ok=R2Assert(!R2QuoteCost(100,100.08,100.04,0),"zero_atr_rejected") && ok;
   ResetR2State();
   if(ok) Print("R2_NATIVE_FIXTURES_PASS checks=",r2FixtureChecks," preset=",InpEntryStrength);
   return ok;
}
