from clause_analysis import analyze_recovery_clause, analyze_relationship_clause


def test_clause_analysis_preserves_exact_relationship_term():
    analysis = analyze_relationship_clause("My dad is not aware about my drinking.")

    assert analysis.mentions == ["dad"]
    assert analysis.primary_mention == "dad"
    assert analysis.tone == "secrecy"
    assert "dad is not aware" in analysis.clause_text.lower()


def test_clause_analysis_detects_conflict_tone_from_relationship_clause():
    analysis = analyze_relationship_clause("My mom is hating this idea about my drinking.")

    assert analysis.mentions == ["mom"]
    assert analysis.tone == "conflict"
    assert analysis.evidence == "hating"


def test_clause_analysis_detects_concern_tone_locally():
    analysis = analyze_relationship_clause("I drank again and my wife is worried about me.")

    assert analysis.mentions == ["wife"]
    assert analysis.tone == "concern"


def test_clause_analysis_defaults_to_presence_when_no_tone_marker_exists():
    analysis = analyze_relationship_clause("My brother knows about the drinking.")

    assert analysis.mentions == ["brother"]
    assert analysis.tone == "presence"


def test_recovery_clause_analysis_detects_change_readiness():
    analysis = analyze_recovery_clause("I want to stop drinking before this gets worse.")

    assert analysis.theme == "change_readiness"
    assert analysis.evidence == "want to stop"


def test_recovery_clause_analysis_detects_lapse():
    analysis = analyze_recovery_clause("I slipped and had a drink last night.")

    assert analysis.theme == "lapse"


def test_recovery_clause_analysis_detects_shame():
    analysis = analyze_recovery_clause("I feel ashamed that I drank again.")

    assert analysis.theme == "shame"


def test_recovery_clause_analysis_detects_pressure():
    analysis = analyze_recovery_clause("Everyone expects me to fix this and I feel pressured.")

    assert analysis.theme == "pressure"