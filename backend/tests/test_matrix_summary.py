from app.services.matrix_summary import matrix_summary


def _cells():
    return [
        {"clo_id": 1, "bloom_level": "remember", "difficulty": "easy", "count": 4, "points_each": 0.5},
        {"clo_id": 2, "bloom_level": "apply", "difficulty": "medium", "count": 4, "points_each": 1.0},
        {"clo_id": 3, "bloom_level": "analyze", "difficulty": "hard", "count": 2, "points_each": 2.0},
    ]


def test_totals_and_weights():
    r = matrix_summary(_cells(), declared_points=10)
    assert r["total_questions"] == 10
    assert r["total_points"] == 10.0  # 2 + 4 + 4
    assert r["ok"] is True
    # tỷ trọng CLO theo điểm
    assert r["clo_weight"]["1"]["points"] == 2.0
    assert r["clo_weight"]["2"]["percent"] == 40.0


def test_points_mismatch_is_error():
    cells = [{"clo_id": 1, "bloom_level": "remember", "difficulty": "easy", "count": 2, "points_each": 1}]
    r = matrix_summary(cells, declared_points=10)
    assert not r["ok"]
    assert any("Tổng điểm" in e for e in r["errors"])


def test_low_bloom_warning():
    cells = [
        {"clo_id": 1, "bloom_level": "remember", "difficulty": "easy", "count": 8, "points_each": 1},
        {"clo_id": 2, "bloom_level": "apply", "difficulty": "medium", "count": 2, "points_each": 1},
    ]
    r = matrix_summary(cells, declared_points=10)
    assert any("Nhớ/Hiểu" in w for w in r["warnings"])


def test_missing_clo_is_error():
    cells = [{"clo_id": None, "bloom_level": "remember", "difficulty": "easy", "count": 1, "points_each": 10}]
    r = matrix_summary(cells, declared_points=10)
    assert not r["ok"]
    assert any("thiếu CLO" in e for e in r["errors"])


from app.services.matrix_summary import rebalance_points


def _total(cells):
    return round(sum(int(c["count"]) * c["points_each"] for c in cells), 2)


def test_rebalance_scales_to_target():
    cells = [
        {"clo_id": 1, "bloom_level": "remember", "difficulty": "easy", "count": 5, "points_each": 1.0},
        {"clo_id": 2, "bloom_level": "apply", "difficulty": "medium", "count": 5, "points_each": 3.0},
        {"clo_id": 3, "bloom_level": "analyze", "difficulty": "hard", "count": 2, "points_each": 4.0},
    ]
    out = rebalance_points(cells, 100)
    assert _total(out) == 100.0


def test_rebalance_exact_with_single_cell():
    cells = [
        {"clo_id": 1, "bloom_level": "remember", "difficulty": "easy", "count": 3, "points_each": 1.0},
        {"clo_id": 2, "bloom_level": "apply", "difficulty": "medium", "count": 1, "points_each": 2.0},
    ]
    out = rebalance_points(cells, 10)
    assert _total(out) == 10.0


def test_rebalance_zero_points_divides_evenly():
    cells = [
        {"clo_id": 1, "bloom_level": "remember", "difficulty": "easy", "count": 4, "points_each": 0},
        {"clo_id": 2, "bloom_level": "apply", "difficulty": "medium", "count": 1, "points_each": 0},
    ]
    out = rebalance_points(cells, 10)
    assert _total(out) == 10.0


def test_rebalance_target_10_scale():
    cells = [
        {"clo_id": 1, "bloom_level": "remember", "difficulty": "easy", "count": 20, "points_each": 0.5},
        {"clo_id": 2, "bloom_level": "essay", "difficulty": "hard", "count": 2, "points_each": 2.5},
    ]
    out = rebalance_points(cells, 10)
    assert _total(out) == 10.0
