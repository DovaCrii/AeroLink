"""Serial normalization, as ADR-0002 §2 defines it.

The serial reported by DJI is the only key present in all three worlds — the
telemetry, AeroControl's padrón, and the DGAC's RPAS certificate — so it is the
key both systems compare on. That only works if both normalize it identically.

Two rules, and nothing else:

- **Upper-case, no whitespace.** Whitespace is stripped from inside the value
  too, not just the ends: real aircraft carry a spurious space mid-serial.
- **No length assumptions.** 20-character (Mavic 3 / Matrice 4) and
  14-character (Matrice 300) serials coexist. Never pad, never truncate.

**No fuzzy matching, ever.** ADR-0002 forbids Levenshtein and `O`↔`0`
substitution by name. Two of the sixteen real aircraft differ from their folder
name by exactly one character, and guessing which is right would attribute
telemetry to the wrong airframe — worse than not resolving it at all. That is
settled against the DGAC certificate by a person, not here.

AeroControl applies the same function on its side (`normalize_serial` in
`apps/registry/models.py`).
"""


def normalize_serial(raw: str | None) -> str:
    """The comparable form of a serial. Empty in, empty out."""
    return "".join((raw or "").split()).upper()
