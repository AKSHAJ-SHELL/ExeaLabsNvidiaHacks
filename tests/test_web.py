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
    assert b"arrival_physically_valid: false" in body


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
    (meta / "info.json").write_text('{"arrival_physically_valid": false}')
    status, body = _get(srv, "/download/hero_kitchen")
    assert status == 200
    names = zipfile.ZipFile(io.BytesIO(body)).namelist()
    assert "hero_kitchen/meta/info.json" in names


def _raw_post(srv, body: bytes, length: int, boundary: str = "bnd"):
    import socket

    s = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=10)
    s.sendall((f"POST /jobs HTTP/1.1\r\nHost: x\r\nContent-Type: multipart/form-data; boundary={boundary}\r\n"
               f"Content-Length: {length}\r\nConnection: close\r\n\r\n").encode() + body)
    s.shutdown(socket.SHUT_WR)  # client stops sending: server sees EOF before Content-Length bytes
    data = b""
    while chunk := s.recv(65536):
        data += chunk
    s.close()
    return int(data.split(b" ", 2)[1])


def _part(filename: str, payload: bytes, boundary: str = "bnd", close: bool = True) -> bytes:
    fn = f'; filename="{filename}"' if filename is not None else ""
    return (f'--{boundary}\r\nContent-Disposition: form-data; name="scan"{fn}\r\n\r\n').encode() + payload + (
        f"\r\n--{boundary}--\r\n".encode() if close else b"")


def test_truncated_upload_is_400(server):
    srv, out = server
    body = _part("scan.json", b'{"a": 1}')
    assert _raw_post(srv, body, len(body) + 100) == 400
    assert not (out / "jobs").exists() or not any((out / "jobs").iterdir())


def test_missing_closing_boundary_is_400(server):
    srv, _ = server
    body = _part("scan.json", b'{"a": 1}', close=False)
    assert _raw_post(srv, body, len(body)) == 400


@pytest.mark.parametrize("filename,payload", [("scan.json", b""), (None, b"{}"), ("", b"{}")])
def test_empty_file_or_no_filename_is_400(server, filename, payload):
    srv, _ = server
    body = _part(filename, payload)
    assert _raw_post(srv, body, len(body)) == 400


def test_room_page_links_sim_dataset(server):
    srv, out = server
    meta = out / "datasets" / "hero_kitchen_sim" / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text(json.dumps({"arrival_generator": "mujoco_sim", "total_episodes": 3,
                                                "arrival_physically_valid": True,
                                                "arrival_families": ["counter_to_sink", "open_drawer"]}))
    status, body = _get(srv, "/rooms/hero_kitchen")
    assert status == 200
    assert b"/download/hero_kitchen_sim" in body and b"mujoco_sim" in body and b"open_drawer" in body


def test_capture_app_upload_reaches_worker(server):
    """CAP-1: the iOS app's request (ios/ArrivalCapture/ArrivalCapture/ArrivalAPI.swift multipartBody)
    with a real CapturedRoom export is queued byte for byte and the worker reads it as RoomPlan."""
    from arrival.jobs.worker import load_upload, room_id_for

    srv, out = server
    boundary = "ArrivalBoundary-3F2504E0-4F89-11D3-9A0C-0305E82C3301"
    payload = (REPO / "tests" / "fixtures" / "roomplan" / "amal.json").read_bytes()
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="scan"; filename="kitchen_a.json"\r\n'
        "Content-Type: application/json\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    conn.request("POST", "/jobs", body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                          "Accept": "application/json"})
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    assert resp.status == 202
    job_dir = out / "jobs" / data["id"]
    assert (job_dir / "upload.bin").read_bytes() == payload
    status = json.loads((job_dir / "status.json").read_text())
    room_id = room_id_for(status["filename"], data["id"])
    assert room_id == f"kitchen_a_{data['id']}"
    bundle = load_upload(job_dir / "upload.bin", room_id)
    assert bundle["geometry_source"] == "roomplan"
    assert bundle["room_id"] == room_id
    assert bundle["walls"]


def test_serve_host_flag():
    from arrival.cli import build_parser

    assert build_parser().parse_args(["serve"]).host == "127.0.0.1"
    assert build_parser().parse_args(["serve", "--host", "0.0.0.0"]).host == "0.0.0.0"


def test_non_object_status_does_not_break_index(server):
    srv, out = server
    d = out / "jobs" / "job_deadbeef"
    d.mkdir(parents=True)
    (d / "status.json").write_text("[1]")
    status, _ = _get(srv, "/")
    assert status == 200


def test_job_download_streams_zip(server):
    import json as _json

    srv, out = server
    d = out / "jobs" / "job_cafe0001"
    d.mkdir(parents=True)
    payload = b"PK-not-really-but-bytes" * 100000
    (d / "dataset.zip").write_bytes(payload)
    (d / "status.json").write_text(_json.dumps({"id": "job_cafe0001", "status": "done", "room_id": "r", "zip": "x"}))
    status, body = _get(srv, "/jobs/job_cafe0001/download")
    assert status == 200 and body == payload
