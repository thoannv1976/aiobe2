from app.services.alignment import (
    check_outline_alignment_pure,
    check_program_plo_coverage_pure,
)


def test_outline_alignment_ok():
    res = check_outline_alignment_pure(
        clo_codes=["CLO1", "CLO2"],
        clo_to_plos={"CLO1": ["PLO1"], "CLO2": ["PLO2"]},
        assessments=[
            {"name": "GK", "weight": 40, "clos": ["CLO1"]},
            {"name": "CK", "weight": 60, "clos": ["CLO2"]},
        ],
        lesson_clo_sets=[["CLO1"], ["CLO2"]],
    )
    assert res.ok
    assert res.errors == []


def test_outline_clo_without_plo_is_error():
    res = check_outline_alignment_pure(
        clo_codes=["CLO1"],
        clo_to_plos={"CLO1": []},
        assessments=[{"name": "CK", "weight": 100, "clos": ["CLO1"]}],
        lesson_clo_sets=[["CLO1"]],
    )
    assert not res.ok
    assert any("PLO" in e for e in res.errors)


def test_outline_weight_must_be_100():
    res = check_outline_alignment_pure(
        clo_codes=["CLO1"],
        clo_to_plos={"CLO1": ["PLO1"]},
        assessments=[{"name": "CK", "weight": 80, "clos": ["CLO1"]}],
        lesson_clo_sets=[["CLO1"]],
    )
    assert not res.ok
    assert any("100" in e for e in res.errors)


def test_outline_clo_not_assessed_is_error():
    res = check_outline_alignment_pure(
        clo_codes=["CLO1", "CLO2"],
        clo_to_plos={"CLO1": ["PLO1"], "CLO2": ["PLO1"]},
        assessments=[{"name": "CK", "weight": 100, "clos": ["CLO1"]}],
        lesson_clo_sets=[["CLO1"], ["CLO2"]],
    )
    assert not res.ok
    assert any("CLO2" in e and "đánh giá" in e for e in res.errors)


def test_outline_clo_not_taught_is_warning():
    res = check_outline_alignment_pure(
        clo_codes=["CLO1"],
        clo_to_plos={"CLO1": ["PLO1"]},
        assessments=[{"name": "CK", "weight": 100, "clos": ["CLO1"]}],
        lesson_clo_sets=[[]],
    )
    assert res.ok  # chỉ là cảnh báo
    assert any("buổi dạy" in w for w in res.warnings)


def test_program_coverage_needs_master():
    res = check_program_plo_coverage_pure(
        plo_codes=["PLO1", "PLO2"],
        course_plo=[
            {"course_code": "C1", "plo_code": "PLO1", "level": "M"},
            {"course_code": "C2", "plo_code": "PLO2", "level": "R"},
        ],
    )
    assert res.ok  # đủ phủ nhưng PLO2 thiếu Master -> warning
    assert any("PLO2" in w and "Master" in w for w in res.warnings)


def test_program_coverage_uncovered_is_error():
    res = check_program_plo_coverage_pure(
        plo_codes=["PLO1", "PLO2"],
        course_plo=[{"course_code": "C1", "plo_code": "PLO1", "level": "M"}],
    )
    assert not res.ok
    assert any("PLO2" in e for e in res.errors)
