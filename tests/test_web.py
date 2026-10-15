import http.client
import json
import threading
from pathlib import Path

import pytest

from arrival.jobs.queue import check_upload_size
from arrival.web.app import make_server

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def server(tmp_path):
    out = tmp_path / "out"
    srv = make_server(port=0, out_dir=out, scans_dir=REPO / "scans")
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv, out
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _get(srv, path):
    conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, body


def test_index_lists_hero_kitchen(server):
    srv, _ = server
    status, body = _get(srv, "/")
    assert status == 200
    assert b"hero_kitchen" in body


def test_room_page_shows_flag(server):
    srv, _ = server
    status, body = _get(srv, "/rooms/hero_kitchen")
    assert status == 200
    assert b"walkin_physically_valid: false" in body


def test_post_job_queues(server):
    srv, out = server
    boundary = "----arrivaltestboundary"
    payload = b'{"room_id": "uploaded"}'
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="scan"; filename="scan.json"\r\n'
        "Content-Type: application/json\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    conn.request("POST", "/jobs", body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    assert resp.status == 202
    assert data["status"] == "queued"
    job_dir = out / "jobs" / data["id"]
    status = json.loads((job_dir / "status.json").read_text())
    assert status["status"] == "queued"
    assert status["bytes"] == len(payload)
    assert (job_dir / "upload.bin").read_bytes() == payload

    code, got = _get(srv, data["status_url"])
    assert code == 200
    assert json.loads(got)["id"] == data["id"]


def test_post_without_scan_field_is_400(server):
    srv, _ = server
    boundary = "b0undary"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"other\"\r\n\r\nx\r\n"
            f"--{boundary}--\r\n").encode()
    conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    conn.request("POST", "/jobs", body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    resp.read()
    conn.close()
    assert resp.status == 400


def test_upload_limit():
    assert check_upload_size(201 * 1024 * 1024) is False
    assert check_upload_size(1024) is True


def test_download_missing_is_404(server):
    srv, _ = server
    status, _ = _get(srv, "/download/nonexistent")
    assert status == 404
    status, _ = _get(srv, "/download/..%2F..")
    assert status == 404


def test_download_zip(server):
    import io
    import zipfile

    srv, out = server
    meta = out / "datasets" / "hero_kitchen" / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text('{"walkin_physically_valid": false}')
    status, body = _get(srv, "/download/hero_kitchen")
    assert status == 200
    names = zipfile.ZipFile(io.BytesIO(body)).namelist()
    assert "hero_kitchen/meta/info.json" in names
