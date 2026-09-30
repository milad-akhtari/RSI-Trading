from types import SimpleNamespace as NS

from automation.mt5_client import MT5Broker
from tests.test_execution_engine import make_settings


class Module:
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    TRADE_RETCODE_INVALID_FILL = 10030
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def order_check(self, request):
        return NS(retcode=0)
    def order_send(self, request):
        self.calls.append(request)
        return self.responses.pop(0)
    def last_error(self):
        return (1, "synthetic transport error")


def adapter(module):
    broker = MT5Broker(make_settings())
    broker.mt5 = module
    return broker


def test_unknown_order_result_does_not_try_a_second_filling_mode():
    module = Module([None])
    result = adapter(module)._send_with_filling_fallback({"action": 1})
    assert result.uncertain and len(module.calls) == 1


def test_only_definite_invalid_fill_can_try_another_mode():
    module = Module([NS(retcode=10030), NS(retcode=10009, order=1, deal=2, comment="done")])
    result = adapter(module)._send_with_filling_fallback({"action": 1})
    assert result.ok
    assert [call["type_filling"] for call in module.calls] == [module.ORDER_FILLING_FOK, module.ORDER_FILLING_IOC]


def test_partial_fill_never_uses_return_or_retries_remaining_volume():
    module = Module([NS(retcode=10010, order=1, deal=2, comment="partial")])
    result = adapter(module)._send_with_filling_fallback({"action": 1})
    assert result.ok and len(module.calls) == 1
    assert module.calls[0]["type_filling"] != module.ORDER_FILLING_RETURN


def test_definite_non_filling_rejection_is_not_resubmitted():
    module = Module([NS(retcode=10019, comment="not enough margin")])
    result = adapter(module)._send_with_filling_fallback({"action": 1})
    assert not result.ok and not result.uncertain and len(module.calls) == 1
