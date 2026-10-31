import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Zipilogue"))
import dialogue_lab as d  # noqa: E402
from shared.qa_fidelity import Probe, matches  # noqa: E402

NFD = lambda s: unicodedata.normalize("NFD", s)  # noqa: E731


def test_encode_nfd_does_not_hit_base_letters():
    assert d.encode(NFD("café"), [{"long": "cafe", "short": "c"}]) == "café"


def test_encode_nfd_matches_nfc_rule():
    assert d.encode(NFD("café crème ok"), [{"long": "café crème", "short": "cc"}]) == "cc ok"


def test_validate_accepts_nfd_training():
    rules = d.validate_mapping({"mapping": [{"long": "café crème", "short": "Q1"}]},
                               [{"text": NFD("Order café crème now.")}])
    assert rules == [{"long": "café crème", "short": "Q1"}]


def test_matches_nfd_answer():
    assert matches(Probe("term", "q", "München"), NFD("Er wohnt in München."))
    assert matches(Probe("id", "q", "Ä-1"), NFD("Ä-1"))


def test_matches_rejects_accented_neighbor():
    assert not matches(Probe("term", "q", "Rene"), NFD("René"))
