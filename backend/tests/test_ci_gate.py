# [TESTE] Falha proposital para validar a proteção de branch. Não mergear.


def test_ci_gate_must_fail():
    assert 1 + 1 == 3, "falha proposital: PR de teste da proteção de branch"
