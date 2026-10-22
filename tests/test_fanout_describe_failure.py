import json

from arrival.jobs.fanout import FanoutConfig
from arrival.jobs.fanout_status import StatusRecorder, status_key

CFG = FanoutConfig("run", 1, "room", "counter_to_sink", 1, 0, 32, 0, "scans")


class Backend:
    def __init__(self):
        self.objects = {}

    def exists(self, key):
        return key in self.objects

    def put_object(self, key, data):
        self.objects[key] = data

    def submit(self, cfg, i):
        return "job-1"

    def describe(self, job_id):
        raise RuntimeError("metadata service unavailable")


def test_optional_description_failure_keeps_submitted_job():
    backend = Backend()
    recorder = StatusRecorder(backend)
    assert recorder.submit(CFG, 0) == "job-1"
    record = json.loads(backend.objects[status_key(CFG, 0)])
    assert record["attempts"][0]["job_id"] == "job-1"
    assert record["attempts"][0]["resources"] is None
