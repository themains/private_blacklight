import importlib.util
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import Mock

import pytest
import requests


@pytest.fixture
def probe(monkeypatch):
    folder = Path(__file__).resolve().parents[1] / "scripts/collect/selection_audit"
    monkeypatch.syspath_prepend(str(folder))
    spec = importlib.util.spec_from_file_location(
        "probe", folder / "03_probe_and_rescan.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.socket, "getaddrinfo", lambda *args: [])
    return module


@pytest.mark.parametrize(
    "url,status,expected",
    [
        ("https://example.com", 200, "live"),
        ("https://example.com", 503, "http_error"),
        ("https://other.org", 200, "redirect"),
        ("https://wired.meraki.com", 200, "network_filtered"),
    ],
)
def test_probe_classifies_responses(probe, monkeypatch, url, status, expected):
    response = Mock(status_code=status, url=url)
    response.iter_content.return_value = iter([b"<title> Test  page </title>"])
    get = Mock(return_value=response)
    monkeypatch.setattr(probe.requests, "get", get)
    row = probe.probe_domain("example.com")
    assert row["probe_status"] == expected
    assert row["page_title"] == "Test page"
    assert row["http_status"] == status
    assert get.call_args.kwargs["timeout"] == probe.config.PROBE_TIMEOUT
    response.close.assert_called_once()


def test_probe_falls_back_to_http(probe, monkeypatch):
    response = Mock(status_code=200, url="http://example.com")
    response.iter_content.return_value = iter([])
    get = Mock(side_effect=[requests.ConnectionError("TLS failed"), response])
    monkeypatch.setattr(probe.requests, "get", get)
    assert probe.probe_domain("example.com")["probe_status"] == "live"
    assert [call.args[0] for call in get.call_args_list] == [
        "https://example.com",
        "http://example.com",
    ]


def test_dns_failure_does_not_send_http(probe, monkeypatch):
    monkeypatch.setattr(
        probe.socket, "getaddrinfo", Mock(side_effect=socket.gaierror("missing"))
    )
    get = Mock(side_effect=AssertionError("unexpected network request"))
    monkeypatch.setattr(probe.requests, "get", get)
    row = probe.probe_domain("example.com")
    assert row["probe_status"] == "dead"
    assert row["dns_resolves"] is False
    get.assert_not_called()


def test_requests_urllib3_streaming_integration():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"<title>local fixture</title>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with requests.Session() as session:
            session.trust_env = False
            with session.get(
                f"http://127.0.0.1:{server.server_port}", stream=True, timeout=5
            ) as response:
                response.raise_for_status()
                assert (
                    b"".join(response.iter_content(8))
                    == b"<title>local fixture</title>"
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
