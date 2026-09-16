from app.services.alerts import alert_level_for_score, compute_intervention_score


def test_thresholds_match_document_table():
    assert alert_level_for_score(0.30) is None          # < 0.45 -> silent/store
    assert alert_level_for_score(0.50) == "info"         # 0.45-0.60 -> brief
    assert alert_level_for_score(0.65) == "advisory"      # 0.60-0.75 -> advisory
    assert alert_level_for_score(0.80) == "warning"       # 0.75-0.90 -> warning
    assert alert_level_for_score(0.95) == "command_alert"  # > 0.90 -> command alert


def test_boundary_values_are_inclusive_on_the_lower_edge():
    assert alert_level_for_score(0.45) == "info"
    assert alert_level_for_score(0.60) == "advisory"
    assert alert_level_for_score(0.75) == "warning"
    assert alert_level_for_score(0.90) == "warning"  # "> 0.90", not ">="
    assert alert_level_for_score(0.9001) == "command_alert"


def test_red_line_forces_command_alert_regardless_of_score():
    assert alert_level_for_score(0.10, red_line=True) == "command_alert"


def test_score_is_clamped_to_unit_interval():
    high = compute_intervention_score(
        impact=1, urgency=1, cost_of_delay=1, irreversibility=1,
        dependency_centrality=1, strategic_alignment=1, confidence=1,
    )
    assert high == 1.0

    low = compute_intervention_score(
        impact=0, urgency=0, cost_of_delay=0, irreversibility=0,
        dependency_centrality=0, strategic_alignment=0, confidence=0, attention_cost=1,
    )
    assert low == 0.0


def test_attention_cost_reduces_score():
    base = compute_intervention_score(
        impact=0.8, urgency=0.8, cost_of_delay=0.5, irreversibility=0.3,
        dependency_centrality=0.3, strategic_alignment=0.5, confidence=0.5,
    )
    with_cost = compute_intervention_score(
        impact=0.8, urgency=0.8, cost_of_delay=0.5, irreversibility=0.3,
        dependency_centrality=0.3, strategic_alignment=0.5, confidence=0.5,
        attention_cost=0.2,
    )
    assert with_cost < base
