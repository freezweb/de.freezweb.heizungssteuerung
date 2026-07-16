from pathlib import Path
for p in ["src/heizung/__main__.py", "tests/test_oelbrenner_safety.py"]:
    compile(Path(p).read_text(encoding="utf-8"), p, "exec")
print("compile ok")
