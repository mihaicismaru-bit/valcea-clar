"""Double-click via Install.cmd from a normal Windows session."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from administratie.ramnicu_valcea.windows_install import main

if __name__ == "__main__":
    raise SystemExit(main())
