import os
import shutil
from pathlib import Path

root = Path("D:/project/trader-bot")
versions_dir = root / "versions"
versions_dir.mkdir(exist_ok=True)

keep_root_files = {
    "QuantumTitan_v23_LondonRetestBreakout.mq5",
    "QuantumTitan_v23_LondonRetestBreakout.ex5",
    "README.md",
    "AGENTS.md",
    "GEMINI.md",
    ".gitignore",
}

# Find all other EA and probe files in root
moved = []
for p in root.iterdir():
    if p.is_file() and p.name not in keep_root_files:
        # Move other .mq5 and .ex5 to versions/
        if p.suffix.lower() in [".mq5", ".ex5"]:
            dest = versions_dir / p.name
            shutil.move(str(p), str(dest))
            moved.append(p.name)
        # Move older logs and compile logs to versions/logs/
        elif p.name.endswith(".log") and p.name != "compile.log":
            logs_dir = versions_dir / "logs"
            logs_dir.mkdir(exist_ok=True)
            shutil.move(str(p), str(logs_dir / p.name))
            moved.append(p.name)
        elif p.name.startswith("OPENCODE_HANDOFF_"):
            docs_dir = root / "docs"
            shutil.move(str(p), str(docs_dir / p.name))
            moved.append(p.name)

print(f"Moved {len(moved)} files to versions/ or docs/:")
for m in moved:
    print(" -", m)
