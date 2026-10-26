"""PDF text extraction subprocess; caller enforces a 45-second timeout."""
from pathlib import Path
import sys


def main():
    from pypdf import PdfReader
    reader = PdfReader(Path(sys.argv[1]), strict=False)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("Encrypted PDF requires manual review")
    sys.stdout.buffer.write("\n".join(page.extract_text() or "" for page in reader.pages).encode("utf-8"))


if __name__ == "__main__":
    main()
