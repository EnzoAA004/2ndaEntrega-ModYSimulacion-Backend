import pytest

from app.services.numerical_methods import euler, heun, rk4


def exponential_decay(_t, y, _params):
    return -y


def test_euler_accepts_scalar_state():
    t, y = euler(exponential_decay, 1.0, 0, 1, 0.1)
    assert len(t) == len(y)
    assert y[-1] < 1.0
    assert y[-1] >= 0.0


def test_rk4_is_close_for_exponential_decay():
    _t, y = rk4(exponential_decay, 1.0, 0, 1, 0.05)
    assert y[-1] == pytest.approx(0.367879, rel=1e-4)


def test_heun_handles_vector_state():
    def f(_t, y, _params):
        return [-y[0], -2 * y[1]]

    _t, y = heun(f, [1.0, 2.0], 0, 1, 0.1)
    assert len(y[-1]) == 2
    assert y[-1][0] >= 0
    assert y[-1][1] >= 0

