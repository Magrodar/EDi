import asyncio

from app.llm.stub import StubExtractionProvider

provider = StubExtractionProvider()


def run(text: str):
    return asyncio.run(provider.extract(text))


def test_detects_commitment_cue():
    result = run("I'll send the updated forecast to the supplier by Friday.")
    assert len(result.commitments) == 1
    assert "forecast" in result.commitments[0].title.lower()
    assert result.commitments[0].confidence < 0.65  # stub stays conservative


def test_detects_risk_cue():
    result = run("There is a risk that RM-X may miss the weekly production plan.")
    assert len(result.risks) == 1
    assert result.risks[0].needs_review is True


def test_severity_words_bump_risk_impact():
    mild = run("This might delay the shipment slightly.")
    severe = run("This is a critical risk that might delay the shipment badly.")
    assert severe.risks[0].impact > mild.risks[0].impact


def test_decision_cue_does_not_also_become_a_commitment():
    result = run("We decided to go with Supplier B for RM-X starting next month.")
    assert len(result.decisions) == 1
    assert len(result.commitments) == 0


def test_neutral_sentence_extracts_nothing():
    result = run("The weather was nice today.")
    assert result.facts == []
    assert result.commitments == []
    assert result.risks == []
    assert result.decisions == []


def test_fact_extraction_from_expects_pattern():
    result = run("The supplier expects arrival of RM-X on 2026-09-22.")
    assert len(result.facts) == 1
    fact = result.facts[0]
    assert fact.subject_label.lower().startswith("the supplier")
    assert fact.effective_from is not None
    assert fact.effective_from.year == 2026
    assert fact.effective_from.month == 9
    assert fact.effective_from.day == 22
