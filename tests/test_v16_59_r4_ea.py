"""Static contract checks, not a substitute for MT5 execution parity tests."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / 'QuantumTitan_v16_59_R4StateTransition.mq5').read_text()


class R4EAContract(unittest.TestCase):
    def test_demo_and_hedging_restrictions(self):
        self.assertIn('ACCOUNT_TRADE_MODE_DEMO', SOURCE)
        self.assertIn('ACCOUNT_MARGIN_MODE_RETAIL_HEDGING', SOURCE)
        self.assertIn('InpTargetAccount==0', SOURCE)
        self.assertIn('if(!Authorized()) return', SOURCE)

    def test_nominal_constants(self):
        for token in ['MAGIC=991659', 'LOTS=0.01', 'spread>40.0',
                      'minute>=1080 || minute<117', 'completed<3',
                      'latestRatio<0.5 || latestRatio>1.5',
                      '0.35*atr', '1.5*atr']:
            self.assertIn(token, SOURCE)

    def test_closed_bar_causal_processing(self):
        self.assertIn('start,current-1,bars', SOURCE)
        self.assertIn('current-lastProcessed!=60', SOURCE)
        self.assertIn('copied!=1', SOURCE)
        self.assertIn('timeRing[(ringNext+j-1)%120]!=60', SOURCE)

    def test_indicator_seed_and_median(self):
        for token in ['sumFast/6.0', 'sumSlow/24.0', 'sumTR/14.0',
                      '(atr*13.0+tr)/14.0', '(sorted[59]+sorted[60])/2.0']:
            self.assertIn(token, SOURCE)

    def test_no_active_profit_lock_or_nominal_stop(self):
        self.assertIn('InpEmergencyStop=false', SOURCE)
        self.assertNotIn('PositionModify(', SOURCE)
        self.assertNotIn('RiskGuardian', SOURCE)

    def test_close_before_entry_and_restart_recovery(self):
        body = SOURCE.split('void OnTick()', 1)[1]
        self.assertLess(body.index('CloseMaturePositions();'), body.index('current==lastBar'))
        self.assertIn('POSITION_TIME', SOURCE)
        self.assertIn('OwnPositions()>0', SOURCE)


if __name__ == '__main__':
    unittest.main()
