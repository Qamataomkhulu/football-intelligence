from backend.intelligence.consensus import (
    calculate_consensus_gap,
    devig_three_way,
    devig_two_way,
    rank_gaps,
)


def test_consensus_gap_matches_design_doc_example():
    # Chelsea WIN market=67%, model=49% -> gap = -18pp
    gap = calculate_consensus_gap("WIN_AWAY", model_probability=0.49, market_probability=0.67)
    assert round(gap.gap_pp, 0) == -18
    assert gap.direction == "market_overpriced"


def test_consensus_gap_brentford_example():
    # Brentford 1X market=58%, model=77% -> gap = +19pp
    gap = calculate_consensus_gap("1X", model_probability=0.77, market_probability=0.58)
    assert round(gap.gap_pp, 0) == 19
    assert gap.direction == "market_underpriced"


def test_devig_three_way_sums_to_one():
    h, d, a = devig_three_way(2.0, 3.5, 4.0)
    assert abs((h + d + a) - 1.0) < 1e-9


def test_devig_two_way_sums_to_one():
    a, b = devig_two_way(1.9, 2.0)
    assert abs((a + b) - 1.0) < 1e-9


def test_rank_gaps_filters_and_sorts_by_absolute_size():
    gaps = [
        calculate_consensus_gap("A", 0.5, 0.48),   # tiny gap
        calculate_consensus_gap("B", 0.7, 0.5),    # big gap
        calculate_consensus_gap("C", 0.3, 0.45),   # moderate negative gap
    ]
    ranked = rank_gaps(gaps, min_gap_pp=10)
    assert [g.outcome for g in ranked] == ["B", "C"]
