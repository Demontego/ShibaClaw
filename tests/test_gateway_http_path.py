from shibaclaw.cli.gateway import parse_http_target, path_segment, suffixed_job_id


def test_parse_http_target_drops_query():
    assert parse_http_target("POST /api/chat?x=1 HTTP/1.1") == ("POST", "/api/chat")
    assert parse_http_target("GET /health HTTP/1.0") == ("GET", "/health")


def test_path_segment_rejects_extra_slash():
    assert path_segment("/api/automation/jobs/abc", "/api/automation/jobs/") == "abc"
    assert path_segment("/api/automation/jobs/abc/update", "/api/automation/jobs/") is None


def test_suffixed_job_id():
    assert suffixed_job_id("/api/automation/jobs/abc/update", "update") == "abc"
    assert suffixed_job_id("/api/automation/jobs/abc/update/extra", "update") is None
