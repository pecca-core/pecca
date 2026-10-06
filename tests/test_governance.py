import pytest

from pecca.core.errors import GovernanceError
from pecca.governance.gates import check_gate, parse_gate


@pytest.mark.parametrize(
    "bad",
    [
        "__import__('os').system('x') > 1",
        "agreement >= 0.9 or rows > 1",
        "eval(1) == 1",
        "agreement >= abs(1)",
        "nonsense >= 1",
        "agreement",
        "",
        "rows >= 1; rows >= 2",
        "rows >= 0x10",
        "agreement >= 0.9 and (rows > 1)",
    ],
)
def test_gate_parser_rejects_non_gates(bad):
    with pytest.raises(GovernanceError):
        parse_gate(bad)


def test_gate_parser_accepts_and():
    assert len(parse_gate("agreement >= 0.90 & shadow_days >= 14")) == 2
    assert len(parse_gate("rows >= 2000 and cv_metric > 0.85")) == 2
    assert len(parse_gate("rows >= 2000 && cv_metric > 0.85")) == 2


def test_check_gate_values_and_missing():
    assert check_gate("agreement >= 0.9", {"agreement": 0.95})[0]
    ok, msg = check_gate("agreement >= 0.9", {"agreement": 0.5})
    assert not ok and "0.5" in msg
    ok, msg = check_gate("agreement >= 0.9", {})
    assert not ok and "no data" in msg
