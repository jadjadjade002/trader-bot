import importlib.util
from pathlib import Path
import pytest
import csv

spec=importlib.util.spec_from_file_location('v23_eval',Path(__file__).parents[1]/'research/analyze_v23_backtest.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def deal(ticket,entry,volume,profit=0,commission=0,fee=0,swap=0,position=2):
    return dict(ticket=str(ticket),position=str(position),time_msc=str(1777856520201+ticket),
                type='0' if entry==0 else '1',entry=str(entry),reason='3',magic='992300',symbol='XAUUSD',
                volume=str(volume),price='4600',profit=str(profit),commission=str(commission),swap=str(swap),fee=str(fee),comment='')

def test_entry_costs_and_partial_exits_grouped_once():
    trades,cash=module.parse_deals([deal(2,0,.02,commission=-.4,fee=-.1),
                                  deal(3,1,.01,profit=2,commission=-.2,swap=-.3),
                                  deal(4,1,.01,profit=-1,commission=-.2,fee=-.1)])
    assert not cash and len(trades)==1
    assert trades[0]['net']==pytest.approx(-.3)
    result=module.bucket(trades)
    assert result['losses']==1 and result['profit']==1 and result['net_profit_factor']==0

@pytest.mark.parametrize('rows',[
    [deal(3,1,.01)],
    [deal(2,0,.01),deal(3,1,.02)],
    [deal(2,0,.01),deal(3,0,.01,position=3)],
    [deal(2,0,.01)],
    [deal(2,0,.01),deal(3,2,.01)],
])
def test_unsupported_or_incomplete_positions_fail_closed(rows):
    with pytest.raises(ValueError): module.parse_deals(rows)

def test_foreign_or_nonfinite_cost_rejected():
    row=deal(2,0,.01);row['magic']='1'
    with pytest.raises(ValueError):module.parse_deals([row])
    with pytest.raises(ValueError):module.parse_deals([deal(2,0,.01,fee='NaN')])

def test_signal_deal_join_survives_minute_boundary_and_missing_other_callback(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'BASE',tmp_path)
    rows=[dict(bar='2026.05.04 12:00:00',original='1',closeback='0',gate='attempt',deal_ticket='2'),
          dict(bar='2026.05.04 12:01:00',original='1',closeback='1',gate='holding',deal_ticket='0'),
          dict(bar='2026.05.04 12:02:00',original='0',closeback='1',gate='no_signal',deal_ticket='0')]
    for name,values in [('a',rows),('b',[rows[0],rows[2]])]:
        folder=tmp_path/'runs'/name;folder.mkdir(parents=True)
        with (folder/f'{name}_raw.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(values)
    trade=dict(position=2,open_msc=1777896060100,deals=[{'ticket':2}],net=5,profit=5,commission=0,swap=0,fee=0)
    result=module.candidate_comparison({'name':'a','trades_detail':[trade]},{'name':'b'})
    assert (result['common'],result['removed'],result['new'])==(1,1,1)
    assert result['callback_bars_only_baseline']==1
    assert result['baseline_filled_failing_closeback']['wins']==1
    assert result['unmatched_baseline_positions']==[]
