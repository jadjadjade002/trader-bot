"""R6 source-contract tests; strategy behavior fixtures run inside MT5 MQL tester."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
BUILDER=ROOT/"research/build_candidate_r6.py"
SOURCE=ROOT/"research/ResearchCandidate_R6.mq5"
RUNNER=ROOT/"research/run_candidate_r6.py"
PROTOCOL=ROOT/"docs/CANDIDATE_R6_SIGNAL_PROTOCOL_20261008.md"


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mql_function(text,name):
    match=re.search(r"^(?:void|bool|int|double|long|ulong)\s+"+re.escape(name)+r"\([^\n]*\)\s*\{",text,re.M)
    if match is None:
        raise AssertionError(f"Missing MQL function {name}")
    left=text.index("{",match.start());depth=1;right=left
    while depth:
        right+=1
        if right>=len(text):raise AssertionError(f"Unclosed MQL function {name}")
        depth+=(text[right]=="{")-(text[right]=="}")
    return text[match.start():right+1]


def call_arity(text,marker):
    start=text.index(marker)+len("FileWrite")
    left=text.index("(",start);depth=0;quoted=False;escaped=False;commas=0
    for i in range(left,len(text)):
        ch=text[i]
        if quoted:
            if escaped:escaped=False
            elif ch=="\\":escaped=True
            elif ch=='"':quoted=False
            continue
        if ch=='"':quoted=True
        elif ch=="(":depth+=1
        elif ch==")":
            depth-=1
            if depth==0:return commas+1
        elif ch=="," and depth==1:commas+=1
    raise AssertionError("Unclosed FileWrite call")


class CandidateR6SourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder=load_module("build_candidate_r6",BUILDER)
        cls.runner=load_module("run_candidate_r6",RUNNER)
        cls.source=SOURCE.read_text(encoding="utf-8").replace("\r\n","\n")
        cls.protocol=PROTOCOL.read_text(encoding="utf-8")

    def test_generated_r6_matches_hash_frozen_builder(self):
        self.assertEqual(self.source,self.builder.generate())
        self.assertEqual(self.builder.EXPECTED_R5_SHA256,"98620AC2DFB772FA8EB7926CECAD80B8495E125B930BC0DFB864E932908C3494")

    def test_four_fixed_cells_no_alignment_override_and_common_exits(self):
        rows=self.runner.configurations()
        self.assertEqual([x[2] for x in rows],["f0","f1","v0","v1"])
        self.assertEqual([x[0] for x in rows],[6,6,7,7])
        for _,params,_ in rows:
            self.assertEqual(set(params),{"InpEntryStrength","InpStopLossATRMul","InpTakeProfitRRMul"})
            self.assertEqual(params["InpStopLossATRMul"],1.5)
            self.assertEqual(params["InpTakeProfitRRMul"],2.0)
        self.assertIn("InpMaxHoldBars!=60",self.source)
        self.assertIn("InpMinSLPoints!=150",self.source)
        self.assertIn("!InpEnableHardSL",self.source)
        self.assertIn("!InpEnableMarginGuard",self.source)
        self.assertIn("!InpEnableCircuitBreaker",self.source)

    def test_causal_lookbacks_and_historical_reclaim_contract(self):
        self.assertIn("int historyCount=(InpExperimentMode==7 ? 80 : 23)",self.source)
        self.assertIn("int atrCount=(InpExperimentMode==7 ? 66 : 2)",self.source)
        self.assertIn("CopyR2Rates(historyCount,r)",self.source)
        self.assertIn("CopyBuffer(atrHandle,0,1,atrCount,av)",self.source)
        self.assertIn("R6M5FullyClosed(open,cutoff)",self.source)
        self.assertIn("R6ReadM5At(r[1].time+60",self.source)
        self.assertIn("R6ReadM5At(r[0].time+60",self.source)
        self.assertIn("r[2].close-r[7].close<=-1.25*atrS2",self.source)
        self.assertIn("r[2].close-r[7].close>=1.25*atrS2",self.source)
        self.assertIn("r[2].close<=e9s3 && r[1].close>e9s2",self.source)
        self.assertIn("r[2].close>=e9s3 && r[1].close<e9s2",self.source)
        self.assertIn("R2CostGate(r[0],av[0])",self.source)
        self.assertNotIn("R2CostGate(r[1]",self.source)
        self.assertIn("shifts 7..66",self.source)

    def test_real_mql_fixture_contract_27_plus_20_equals_47(self):
        fixture=mql_function(self.source,"RunR6FixtureTests")
        self.assertEqual(len(re.findall(r"R6Assert\(",fixture)),20)
        self.assertIn('R5_NATIVE_FIXTURES_PASS checks=',self.source)
        self.assertIn('R6_NATIVE_FIXTURES_PASS checks=20',self.source)
        self.assertIn('R6_NATIVE_FIXTURES_TOTAL checks=47 R5=27 R6=20',self.source)
        self.assertIn('!RunR6FixtureTests()',self.source)
        for tag in ("F_buy_direction_fades","F_sell_mirror","F_reclaim_EMA_equality_rejected",
                    "F_missing_M5_history_rejected","F_M5_close_boundary","V_median60",
                    "V_breakout_sell_mirror","V_gap_rejected"):
            self.assertIn(tag,fixture)

    def test_diagnostic_csv_has_one_value_per_header_and_masks_unavailable_features(self):
        header=call_arity(self.source,'FileWrite(diagnosticFile,"bar"')
        row=call_arity(self.source,'FileWrite(diagnosticFile,TimeToString')
        self.assertEqual(header,row)
        self.assertIn('"r6_features_evaluated"',self.source)
        self.assertIn('(r6FeaturesEvaluated ? "true" : "false")',self.source)
        self.assertIn('(InpExperimentMode==5 ? "true" : "false")',self.source)
        self.assertIn('"legacy_r5_fields_applicable"',self.source)
        self.assertIn("R6FeatureText(r6M1ATR,r6FeaturesEvaluated)",self.source)
        self.assertIn("ResetR6SignalDiagnostics();candidateReason=\"not_evaluated_execution_block\"",self.source)
        self.assertIn('if(InpExperimentMode>=6)r6OpportunityStatus="censored_held_position"',self.source)
        self.assertIn('if(InpExperimentMode>=6)r6OpportunityStatus="censored_circuit_breaker"',self.source)

    def test_runner_requires_login_before_any_native_call_and_has_no_auto_activate(self):
        for bad in (None,0,-4,True,5055578643.0,"5055578643"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.runner.validate_tester_login(bad)
        self.assertEqual(self.runner.validate_tester_login(5055578643),5055578643)
        runner_text=RUNNER.read_text(encoding="utf-8")
        self.assertIn('if not args.activate:',runner_text)
        self.assertIn("native.execute",runner_text)

    def test_protocol_freezes_all_survivors_and_release_gates(self):
        self.assertIn("up to all four",self.protocol)
        self.assertIn("7/10 positive months",self.protocol)
        self.assertIn("native equity DD <= V24",self.protocol)
        self.assertIn("Do not reselect after failed confirmation",self.protocol)
        self.assertIn("UNRUN_SCHEDULE_UNVERIFIED",self.protocol)


if __name__=="__main__":
    unittest.main()
