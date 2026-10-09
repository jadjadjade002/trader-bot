"""Native controller must not race a manually opened or relaunched lab."""
import json
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from research import run_v25_native as native


def test_process_probe_returns_identity_not_command_line():
    row = {"ProcessId": 123, "Name": "terminal64.exe"}
    result = CompletedProcess([], 0, json.dumps(row), "")
    with patch.object(native.subprocess, "run", return_value=result) as run:
        assert native.lab_processes() == [row]
    command = run.call_args.args[0][-1]
    assert "Select-Object ProcessId,Name" in command
    assert "CommandLine.Contains" in command
    assert "Stop-Process" not in command
    assert str(native.LAB.resolve()) in command


@pytest.mark.parametrize("payload", ("null", '"bad"', '[{"ProcessId":true,"Name":"terminal64.exe"}]',
                                     '[{"ProcessId":0,"Name":"terminal64.exe"}]',
                                     '[{"ProcessId":1,"Name":"other.exe"}]'))
def test_malformed_process_probe_fails_closed(payload):
    with patch.object(native.subprocess, "run", return_value=CompletedProcess([], 0, payload, "")):
        with pytest.raises(RuntimeError, match="identity"):
            native.lab_processes()


def test_busy_lab_refuses_launch_without_terminating_any_process():
    with patch.object(native, "lab_processes", return_value=[{"ProcessId":9,"Name":"metatester64.exe"}]), \
         patch.object(native.subprocess, "Popen") as launch:
        with pytest.raises(RuntimeError, match="No new launch"):
            native.assert_lab_idle()
        launch.assert_not_called()


def test_bounded_drain_can_observe_normal_shutdown():
    with patch.object(native, "lab_processes", side_effect=[
            [{"ProcessId":9,"Name":"metatester64.exe"}], []]), \
         patch.object(native.time, "sleep") as sleep:
        native.assert_lab_idle(wait_seconds=15)
        sleep.assert_called_once_with(.5)


def test_update_handoff_is_not_a_strategy_result():
    result = native.completion_failure("LiveUpdate start\nTerminal exit with code 0", 0, False)
    assert result["category"] == "NATIVE_RUNTIME_UPDATE_RELAUNCH"
    assert result["accepted"] is False
    assert result["strategy_result_available"] is False


def test_updated_native_completion_requires_terminal_and_agent_proofs():
    journal = ('Tester\tlast test passed with result "successfully finished" in 0:00:29.900\n'
               'Tester\tfinal balance 10130.00 USD\n'
               'Tester\ttest Experts\\AegisPredator_v24.ex5 on XAUUSD,M1 thread finished')
    assert native.completion_ok(journal)
    assert not native.completion_ok(journal.splitlines()[0])
    assert not native.completion_ok(journal.replace("successfully finished", "failed"))
    assert not native.completion_ok(journal.replace("final balance", "unrelated balance"))
    assert not native.completion_ok(journal, optimize=True)
    assert not native.completion_ok(journal + "\nLiveUpdate start")
    assert not native.completion_ok("automatic testing finished\nLiveUpdate start")
