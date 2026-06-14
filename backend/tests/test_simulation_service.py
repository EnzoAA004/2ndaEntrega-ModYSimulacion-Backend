from app.schemas import InfectionWastewaterRequest, ViralDecayRequest
from app.services.simulation_service import infection_wastewater_2d, viral_decay_1d


def test_viral_decay_returns_equilibrium_without_saving():
    result = viral_decay_1d(ViralDecayRequest(S=100, k=0.1, d=0.1, V0=0, t_final=5, step=1, method="rk4", save=False))
    assert result["equilibria"][0]["values"]["V"] == 500
    assert result["stability"]["classification"] == "stable"
    assert len(result["time"]) == len(result["series"]["V"])


def test_infection_wastewater_has_positive_equilibrium_when_beta_gt_gamma():
    payload = InfectionWastewaterRequest(
        beta=0.3,
        K=1000,
        gamma=0.1,
        alpha=50,
        k=0.1,
        d=0.05,
        I0=10,
        V0=0,
        t_final=10,
        step=1,
        save=False,
    )
    result = infection_wastewater_2d(payload)
    assert len(result["equilibria"]) == 2
    assert "I" in result["series"]
    assert "V" in result["series"]
