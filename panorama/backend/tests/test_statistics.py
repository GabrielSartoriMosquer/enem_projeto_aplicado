import pandas as pd
from app.services.statistics import compute_score_statistics


def test_percentile_and_z_score():
    stats = compute_score_statistics(pd.Series([100, 200, 300, 400]), 300)
    assert stats.n == 4
    assert stats.percentile == 75.0
    assert stats.mean == 250.0
    assert stats.z_score is not None


def test_constant_series_has_no_z_score():
    stats = compute_score_statistics(pd.Series([500, 500, 500]), 500)
    assert stats.percentile == 100.0
    assert stats.z_score is None
