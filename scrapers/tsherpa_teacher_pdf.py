"""Deprecated location.

This module moved to extract-textbook-content/tsherpa_teacher_pdf.py.
"""

from pathlib import Path
import runpy


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "extract-textbook-content" / "tsherpa_teacher_pdf.py"
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
