from pathlib import Path
import re

SRC = Path("content/parts/part_b/01_part_b.md")

raw = SRC.read_bytes()

# Decode robustly
for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
    try:
        text = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue
else:
    text = raw.decode("utf-8", errors="replace")

# Normalize ALL newline-like separators to \n
text = text.replace("\r\n", "\n").replace("\r", "\n")
text = text.replace("\u2028", "\n").replace("\u2029", "\n")  # line/paragraph separators
text = text.replace("\x0b", "\n").replace("\x0c", "\n")      # vertical tab / form feed

# Remove invisible chars globally
invisibles = ["\ufeff", "\u200b", "\u200c", "\u200d", "\u2060"]
for ch in invisibles:
    text = text.replace(ch, "")

# Unescape accidental markdown escapes
text = text.replace("\\#", "#").replace("\\-", "-")

# Ensure headings start at column 1 and remove any leading odd whitespace chars
clean_lines = []
for line in text.split("\n"):
    # Strip leading BOM/invisible already removed; now strip only weird unicode spaces
    # Keep normal spaces for non-heading lines
    if line.lstrip().startswith("#"):
        clean_lines.append(line.lstrip())
    else:
        clean_lines.append(line)

text = "\n".join(clean_lines).strip() + "\n"

# Write as clean UTF-8 with \n newlines
SRC.write_text(text, encoding="utf-8", newline="\n")

print("✅ Rewrote file as clean UTF-8 with normalized newlines.")
print("Headings detected by regex after write:")
detected = re.findall(r"(?m)^#{1,3}\s+(.+?)\s*$", text)
print(detected[:20])

# Diagnostic: show codepoints for the first 120 characters
sample = text[:120]
print("First 120 chars repr:", repr(sample))
print("First 120 codepoints:", [hex(ord(c)) for c in sample])