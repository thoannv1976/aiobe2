from app.services.exam_generation import (
    generate_exam_pure,
    validate_matrix_coverage_pure,
)


def _pool():
    qs = []
    qid = 0
    for clo in (1, 2):
        for diff in ("easy", "medium", "hard"):
            for _ in range(5):
                qid += 1
                qs.append({"id": qid, "clo_id": clo, "bloom_level": "apply", "difficulty": diff, "points": 1})
    return qs


def test_generate_ok_and_no_duplicates():
    cells = [
        {"clo_id": 1, "bloom_level": "apply", "difficulty": "easy", "count": 3, "points_each": 2},
        {"clo_id": 2, "bloom_level": "apply", "difficulty": "hard", "count": 2, "points_each": 1},
    ]
    res = generate_exam_pure(cells, _pool(), seed=42)
    assert res.ok
    assert len(res.picked_ids) == 5
    assert len(set(res.picked_ids)) == 5  # không trùng
    assert res.total_points == 3 * 2 + 2 * 1


def test_generate_insufficient_pool_reports_error():
    cells = [{"clo_id": 1, "bloom_level": "apply", "difficulty": "easy", "count": 99}]
    res = generate_exam_pure(cells, _pool(), seed=1)
    assert not res.ok
    assert res.errors


def test_generate_is_deterministic_with_seed():
    cells = [{"clo_id": 1, "bloom_level": "apply", "difficulty": "medium", "count": 3}]
    r1 = generate_exam_pure(cells, _pool(), seed=7)
    r2 = generate_exam_pure(cells, _pool(), seed=7)
    assert r1.picked_ids == r2.picked_ids


def test_matrix_coverage_detects_missing_clo():
    cells = [{"clo_id": 1, "bloom_level": "apply", "difficulty": "easy", "count": 2}]
    missing = validate_matrix_coverage_pure(cells, {1, 2, 3})
    assert len(missing) == 2  # thiếu CLO 2 và 3
