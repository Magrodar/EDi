import pytest

from app.services.promotion import PROMOTION_THRESHOLD, compute_promotion_score


def test_all_max_signals_promotes():
    score = compute_promotion_score(
        strategic_relevance=1.0,
        future_reuse_probability=1.0,
        commitment_or_deadline_weight=1.0,
        risk_or_opportunity_weight=1.0,
        repetition_signal=1.0,
        user_explicitness=1.0,
    )
    assert score == 1.0
    assert score >= PROMOTION_THRESHOLD


def test_all_min_signals_stays_provisional():
    score = compute_promotion_score(
        strategic_relevance=0.0,
        future_reuse_probability=0.0,
        commitment_or_deadline_weight=0.0,
        risk_or_opportunity_weight=0.0,
        repetition_signal=0.0,
        user_explicitness=0.0,
    )
    assert score == 0.0
    assert score < PROMOTION_THRESHOLD


def test_weights_sum_to_one():
    # every weight at 0.5 must return exactly 0.5 -- proves the weights are a partition of unity
    score = compute_promotion_score(
        strategic_relevance=0.5,
        future_reuse_probability=0.5,
        commitment_or_deadline_weight=0.5,
        risk_or_opportunity_weight=0.5,
        repetition_signal=0.5,
        user_explicitness=0.5,
    )
    assert score == 0.5


def test_out_of_range_signal_rejected():
    with pytest.raises(ValueError):
        compute_promotion_score(
            strategic_relevance=1.5,
            future_reuse_probability=0.5,
            commitment_or_deadline_weight=0.5,
            risk_or_opportunity_weight=0.5,
            repetition_signal=0.5,
            user_explicitness=0.5,
        )


def test_document_example_high_strategic_low_everything_else_stays_provisional():
    # A fact linked to a project but with nothing else corroborating it should not
    # silently become canonical -- false memory is worse than missing trivia (doc §9.2).
    score = compute_promotion_score(
        strategic_relevance=1.0,
        future_reuse_probability=0.5,
        commitment_or_deadline_weight=0.3,
        risk_or_opportunity_weight=0.2,
        repetition_signal=0.0,
        user_explicitness=0.3,
    )
    assert score < PROMOTION_THRESHOLD
