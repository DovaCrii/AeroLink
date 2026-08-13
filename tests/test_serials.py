"""ADR-0002 §2: the normalization both systems have to agree on."""

from aerolink.serials import normalize_serial


def test_upper_cases():
    assert normalize_serial("1581f5fhc245") == "1581F5FHC245"


def test_strips_whitespace_inside_not_just_at_the_ends():
    """Real aircraft carry a spurious space mid-serial, so `.strip()` alone
    would leave two values that should compare equal looking different."""
    assert normalize_serial(" 1581 f5fh c245 ") == "1581F5FHC245"


def test_empty_stays_empty():
    assert normalize_serial("") == ""
    assert normalize_serial("   ") == ""
    assert normalize_serial(None) == ""


def test_lengths_are_preserved():
    """20-character (Mavic 3 / Matrice 4) and 14-character (Matrice 300)
    serials coexist. Never pad, never truncate."""
    assert len(normalize_serial("1581F5FHC245700D181D")) == 20
    assert len(normalize_serial("12345678901234")) == 14


def test_nothing_resembling_fuzzy_matching_happens():
    """ADR-0002 forbids O/0 substitution by name: two real aircraft differ from
    their folder by exactly one such character, and guessing would attribute
    telemetry to the wrong airframe."""
    assert normalize_serial("B00D") != normalize_serial("BOOD")
