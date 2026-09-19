import importlib.util
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('report',Path(__file__).parents[1]/'scripts/analyze_v17_report.py')
report=importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

def table_row(values):
    return '<tr>'+''.join('<td>'+str(v)+'</td>' for v in values)+'</tr>'

def fixture(extra_entry=False):
    rows=[['Period:','M1 (2026.08.03 - 2026.08.06)'],['Total Trades:','2'],
          ['Total Net Profit:','0.80'],['Deals']]
    rows.append(['2026.08.03 19:00:00',2,'XAUUSD','buy','in',.01,100,2,-.10,0,0,49.9,'entry'])
    if extra_entry:
        rows.append(['2026.08.03 19:00:01',9,'XAUUSD','buy','in',.01,100,9,0,0,0,49.9,'entry'])
    rows.extend([
        ['2026.08.03 19:01:00',3,'XAUUSD','sell','out',.004,102,3,-.04,0,.80,50.66,'partial'],
        ['2026.08.03 19:02:00',4,'XAUUSD','sell','out',.006,102,4,-.06,0,1.20,51.8,'tp'],
        ['2026.08.04 01:00:00',5,'XAUUSD','sell','in',.01,100,5,0,0,0,51.8,'entry'],
        ['2026.08.04 01:01:00',6,'XAUUSD','buy','out',.01,101,6,0,0,-1,50.8,'sl']])
    return '<table>'+''.join(map(table_row,rows))+'</table>'

class ReportTests(unittest.TestCase):
    def parse(self,content):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'report.htm'
            path.write_text(content,encoding='utf-16')
            return report.analyze(path)

    def test_costs_partials_and_midnight_grouping(self):
        result=self.parse(fixture())
        self.assertEqual(result['trades'],2)
        self.assertEqual(result['win_rate_pct'],50)
        self.assertEqual(result['net'],.8)
        self.assertEqual(result['sessions']['2026-08-03']['trades'],2)
        self.assertEqual(result['full_weekday_windows'],2)
        self.assertEqual(result['sessions']['2026-08-04']['trades'],0)
        self.assertEqual(result['nights_meeting_all_targets'],0)

    def test_concurrency_rejected_not_misreported(self):
        with self.assertRaisesRegex(ValueError,'Concurrent'):
            self.parse(fixture(True))

    def test_closing_after_wake_does_not_count_as_overnight_win(self):
        result=self.parse(fixture().replace('2026.08.04 01:01:00','2026.08.04 02:01:00'))
        self.assertEqual(result['trades'],2)
        self.assertEqual(result['sessions']['2026-08-03']['trades'],1)
        self.assertEqual(result['sessions']['2026-08-03']['carried_past_wake'],1)

    def test_reconciliation_required(self):
        with self.assertRaisesRegex(ValueError,'reconcile'):
            self.parse(fixture().replace('0.80</td></tr>','0.90</td></tr>',1))

    def test_zero_is_not_win(self):
        data=fixture().replace('0.80</td></tr>','1.80</td></tr>',1).replace('<td>-1</td>','<td>0</td>')
        result=self.parse(data)
        self.assertEqual(result['wins'],1)

    def test_wilson_not_certainty_for_small_samples(self):
        lower,upper=report.wilson(16,20)
        self.assertLess(lower,60)
        self.assertGreater(upper,90)

if __name__=='__main__':
    unittest.main()
