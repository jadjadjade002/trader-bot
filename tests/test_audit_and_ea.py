# -*- coding: utf-8 -*-
"""
Verification tests for QuantumSniper 1,000-point institutional audit and EA hardening.
"""
import os
import re

def test_audit_matrix_has_1000_items():
    audit_path = r"D:\project\trader-bot\AUDIT_1000_FLAWS.md"
    assert os.path.exists(audit_path), f"Audit file not found at {audit_path}"
    with open(audit_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Verify 1000 items exist
    matches = re.findall(r"^(\d+)\.\s+\*\*", content, re.MULTILINE)
    assert len(matches) == 1000, f"Expected 1,000 flaws, found {len(matches)}"
    assert matches[0] == "1"
    assert matches[-1] == "1000"

def test_ea_has_hardened_protections():
    ea_path = r"D:\project\trader-bot\QuantumSniper_EA.mq5"
    assert os.path.exists(ea_path), f"EA source file not found at {ea_path}"
    with open(ea_path, "r", encoding="utf-8") as f:
        code = f.read()
    
    # Check NormalizeLot function
    assert "double NormalizeLot(double lot)" in code, "NormalizeLot missing"
    assert "SYMBOL_VOLUME_STEP" in code, "Volume step normalization missing"
    
    # Check Local Calendar Cache
    assert "s_lastCheckTime" in code, "Local calendar cache missing"
    assert "s_cachedResult" in code, "Cached calendar result missing"
    
    # Check Zero-Divide Protection
    assert "m_startingDailyEquity > 0.0" in code, "Zero-divide guard for dailyDD missing"

def test_compile_script_exists():
    compile_script = r"D:\project\trader-bot\scripts\compile.ps1"
    assert os.path.exists(compile_script), "compile.ps1 missing"
