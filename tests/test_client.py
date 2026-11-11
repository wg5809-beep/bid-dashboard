import pytest

from collector.sources.client import DataGoClient, DataGoError
from tests.fakes import FakeResponse, FakeSession, envelope

BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"


def make_client(responses, **kw):
    session = FakeSession(responses)
    sleeps: list[float] = []
    client = DataGoClient("KEY-X", session=session, sleep=sleeps.append, **kw)
    return client, session, sleeps


def test_requires_key():
    with pytest.raises(RuntimeError, match="DATA_GO_KR_SERVICE_KEY not configured"):
        DataGoClient("")


def test_get_items_paginates_until_total():
    client, session, _ = make_client([
        envelope([{"id": 1}, {"id": 2}], total=3),
        envelope([{"id": 3}], total=3),
    ])
    items = client.get_items("svc", BASE, "op", {"a": "1"}, page_size=2)
    assert [i["id"] for i in items] == [1, 2, 3]
    assert len(session.calls) == 2
    assert session.calls[0][0] == f"{BASE}/op"
    assert session.calls[0][1]["pageNo"] == "1" and session.calls[1][1]["pageNo"] == "2"
    assert session.calls[0][1]["numOfRows"] == "2" and session.calls[0][1]["type"] == "json"
    assert session.calls[0][1]["serviceKey"] == "KEY-X" and session.calls[0][1]["a"] == "1"


def test_get_items_single_dict_and_empty_string():
    client, _, _ = make_client([envelope({"id": 7}, total=1), envelope("", total=0)])
    assert client.get_items("svc", BASE, "op", {}) == [{"id": 7}]
    assert client.get_items("svc", BASE, "op", {}) == []


def test_get_items_unwraps_item_key():
    client, _, _ = make_client([envelope({"item": [{"id": 1}]}, total=1)])
    assert client.get_items("svc", BASE, "op", {}) == [{"id": 1}]


def test_json_param_name_for_molit():
    client, session, _ = make_client([envelope([], total=0)])
    client.get_items("kapt", BASE, "op", {}, json_param="_type")
    assert session.calls[0][1]["_type"] == "json" and "type" not in session.calls[0][1]


def test_result_code_03_is_empty():
    client, _, _ = make_client([envelope("", total=0, code="03", msg="NODATA_ERROR")])
    assert client.get_items("svc", BASE, "op", {}) == []


def test_result_code_22_raises_with_code():
    client, _, _ = make_client([envelope("", code="22", msg="LIMITED")])
    with pytest.raises(DataGoError) as exc:
        client.get_items("svc", BASE, "op", {})
    assert exc.value.code == "22" and exc.value.service == "svc"


def test_local_call_limit():
    client, _, _ = make_client([envelope([], total=0), envelope([], total=0)], max_calls_per_service=1)
    client.get_items("svc", BASE, "op", {})
    with pytest.raises(DataGoError) as exc:
        client.get_items("svc", BASE, "op", {})
    assert exc.value.code == "LOCAL_LIMIT"
    assert client.calls == {"svc": 1}


def test_retry_on_500_then_success():
    client, session, sleeps = make_client([
        FakeResponse({}, status_code=500),
        envelope([{"id": 1}], total=1),
    ])
    assert client.get_items("svc", BASE, "op", {}) == [{"id": 1}]
    assert len(session.calls) == 2 and sleeps == [0.6]


def test_retry_gives_up_after_three_failures():
    client, _, sleeps = make_client([FakeResponse({}, status_code=503)] * 4)
    with pytest.raises(DataGoError) as exc:
        client.get_items("svc", BASE, "op", {})
    assert exc.value.code == "HTTP_503" and len(sleeps) == 3


def test_service_key_not_in_repr():
    client, _, _ = make_client([])
    assert "KEY-X" not in repr(client) and "KEY-X" not in str(client)


def test_network_error_message_masks_service_key():
    import requests
    session = FakeSession([requests.ConnectionError("Max retries exceeded with url: /op?serviceKey=K%2BY%2F%3D&pageNo=1")] * 4)
    client = DataGoClient("K+Y/=", session=session, sleep=lambda s: None)
    with pytest.raises(DataGoError) as exc:
        client.get_items("svc", BASE, "op", {})
    text = str(exc.value)
    assert "K+Y/=" not in text and "K%2BY%2F%3D" not in text and "serviceKey=***" in text


def test_redact_masks_query_and_raw_key():
    from collector.sources.client import redact
    assert redact("x?serviceKey=abc&pageNo=1 abc", "abc") == "x?serviceKey=***&pageNo=1 ***"
    assert redact("no key here", None) == "no key here"


def test_missing_header_is_retried_then_succeeds():
    client, session, sleeps = make_client([{}, envelope([{"id": 1}], total=1)])
    assert client.get_items("svc", BASE, "op", {}) == [{"id": 1}]
    assert len(session.calls) == 2 and sleeps == [0.6]


def test_persistent_missing_header_raises_bad_response_with_snippet():
    client, _, _ = make_client([{"error": "gateway busy"}] * 4)
    with pytest.raises(DataGoError) as exc:
        client.get_items("svc", BASE, "op", {})
    assert exc.value.code == "BAD_RESPONSE" and "gateway busy" in str(exc.value)


def gateway(code, msg):
    """공공데이터포털 게이트웨이 오류 봉투(서비스 응답 헤더가 아님)."""
    return {"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"errMsg": msg, "returnAuthMsg": "", "returnReasonCode": code}}}


def test_gateway_http_error_is_retried_then_succeeds():
    client, session, sleeps = make_client([gateway("04", "HTTP_ERROR"), envelope([{"id": 1}], total=1)])
    assert client.get_items("svc", BASE, "op", {}) == [{"id": 1}]
    assert len(session.calls) == 2 and sleeps == [0.6]


def test_persistent_gateway_error_raises_with_gateway_code():
    client, _, sleeps = make_client([gateway("04", "HTTP_ERROR")] * 4)
    with pytest.raises(DataGoError) as exc:
        client.get_items("svc", BASE, "op", {})
    assert exc.value.code == "04" and "HTTP_ERROR" in str(exc.value) and len(sleeps) == 3


def test_gateway_permanent_error_is_not_retried():
    client, session, _ = make_client([gateway("22", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR")])
    with pytest.raises(DataGoError) as exc:
        client.get_items("svc", BASE, "op", {})
    assert exc.value.code == "22" and len(session.calls) == 1


def test_nara_error_envelope_is_permanent_and_keeps_service_code():
    """나라장터 자체 오류 봉투(response 헤더가 아님): 07 입력범위값 초과는 재시도해도 같다."""
    body = {"nkoneps.com.response.ResponseError": {"header": {"resultCode": "07", "resultMsg": "입력범위값 초과 에러"}}}
    client, session, _ = make_client([body])
    with pytest.raises(DataGoError) as exc:
        client.get_items("svc", BASE, "op", {})
    assert exc.value.code == "07" and "입력범위값" in str(exc.value) and len(session.calls) == 1
