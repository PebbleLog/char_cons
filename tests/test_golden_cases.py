from __future__ import annotations

import pytest

from tests.golden_cases import CASES, run_case


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_synthetic_controlled_cases(case):
    result = run_case(case)
    expected = case.expected
    for key in (
        "totalUnits",
        "consistent",
        "inconsistent",
        "unknown",
        "waived",
        "observedOnly",
        "confirmedIssues",
        "suspectedIssues",
        "failedShots",
    ):
        assert result.stats[key] == expected[key], f"{case.name} · {key}"
    assert [
        (issue.unit.shot_code, issue.unit.attribute_id) for issue in result.issues
    ] == expected["issues"], case.name
    for shot_code, conclusion in expected["conclusions"].items():
        assert result.shot_conclusions.get(shot_code) == conclusion, case.name


def test_case_count_is_within_required_range():
    assert 12 <= len(CASES) <= 20
    assert len({case.name for case in CASES}) == len(CASES)
