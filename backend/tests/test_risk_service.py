from app.services.risk_service import classify_risk, risk_from_series


def test_risk_thresholds():
    assert classify_risk(5_000)["risk_level"] == "Bajo"
    assert classify_risk(50_000)["risk_level"] == "Moderado"
    assert classify_risk(500_000)["risk_level"] == "Alto"
    assert classify_risk(2_000_000)["risk_level"] == "Crítico"


def test_trend_increases_category_and_warning():
    result = classify_risk(20_000, trend_7d=80, clinical_cases=0)
    assert result["risk_level"] == "Alto"
    assert result["early_warning"] is True


def test_risk_from_series_computes_trends():
    result = risk_from_series([10_000] * 14 + [30_000])
    assert result["trend_14d"] is not None

