def test_domain_models_import():
    from app.models import Challenge, ChallengeRun, LabEvent, LabSession, Organization, Participant, Team, Workshop
    assert all([Challenge, ChallengeRun, LabEvent, LabSession, Organization, Participant, Team, Workshop])
