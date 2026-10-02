import os
import shutil
from pathlib import Path

root = Path("D:/project/trader-bot")
docs_dir = root / "docs"
scripts_dir = root / "scripts"
versions_dir = root / "versions"
versions_logs = versions_dir / "logs"
versions_logs.mkdir(parents=True, exist_ok=True)
screenshots_dir = root / "docs" / "screenshots"
screenshots_dir.mkdir(parents=True, exist_ok=True)

for p in list(root.iterdir()):
    if p.is_file():
        name = p.name
        if name in [
            "QuantumTitan_v23_LondonRetestBreakout.mq5",
            "QuantumTitan_v23_LondonRetestBreakout.ex5",
            "README.md",
            "AGENTS.md",
            "GEMINI.md",
            ".gitignore",
            "credentials.local.md",
            "HANDOVER_CODEX.local.md"
        ]:
            continue
        
        # Move docs
        if name.startswith("AUDIT_") or name.startswith("PROJECT_CONTEXT"):
            shutil.move(str(p), str(docs_dir / name))
            print("Moved doc:", name)
        # Move scripts
        elif name == "generate_5charts.py":
            shutil.move(str(p), str(scripts_dir / name))
            print("Moved script:", name)
        # Move compile log
        elif name == "compile.log":
            shutil.move(str(p), str(versions_logs / name))
            print("Moved compile log:", name)
        # Move png files
        elif name.endswith(".png"):
            # Move non-hidden to screenshots
            shutil.move(str(p), str(screenshots_dir / name))
            print("Moved screenshot:", name)
        elif name.endswith(".pdf"):
            shutil.move(str(p), str(docs_dir / name))
            print("Moved pdf:", name)

print("Root cleanup complete.")
