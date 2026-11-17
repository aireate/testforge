import pytest

from ai.cli import main
from ai.failure_triage import (
    Failure,
    classify_failure,
    parse_junit,
    render_markdown,
    triage_failures,
)
from ai.llm_client import LlmConfig, enrich

pytestmark = [pytest.mark.unit]

JUNIT_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="1" failures="1" tests="3" time="0.5">
    <testcase classname="tests.api.test_orders" name="test_create_order" time="0.12">
      <failure message="assert 500 == 201">E   assert 500 == 201</failure>
    </testcase>
    <testcase classname="tests.api.test_products" name="test_get_product" time="0.05">
      <error message="requests.exceptions.ConnectionError: Max retries exceeded">E   ConnectionError</error>
    </testcase>
    <testcase classname="tests.api.test_auth" name="test_login" time="0.03" />
  </testsuite>
</testsuites>
"""


@pytest.mark.parametrize(
    "message,detail,expected",
    [
        ("requests.exceptions.ConnectionError: Max retries exceeded", "", "ENVIRONMENT"),
        ("requests.exceptions.ReadTimeout: timed out", "", "ENVIRONMENT"),
        ("assert 503 == 200", "E   assert 503 == 200", "SERVER_ERROR"),
        ("assert 422 == 201", "code=VALIDATION_ERROR", "VALIDATION"),
        ("assert 401 == 200", "UNAUTHORIZED", "AUTHENTICATION"),
        ("assert 403 == 200", "FORBIDDEN", "AUTHORIZATION"),
        ("assert 409 == 201", "OUT_OF_STOCK", "CONFLICT"),
        ("sqlite3.OperationalError: database is locked", "", "DATABASE"),
        ("AssertionError: assert 200 == 201", "E   assert 200 == 201", "ASSERTION"),
        ("KeyError: 'id'", "", "UNKNOWN"),
    ],
    ids=[
        "connection",
        "timeout",
        "server-5xx",
        "validation",
        "authentication",
        "authorization",
        "conflict",
        "database",
        "assertion",
        "unknown",
    ],
)
def test_classify_failure(message, detail, expected):
    result = classify_failure(
        Failure(nodeid="tests.api.test_demo", test_name="test_demo", message=message, detail=detail)
    )
    assert result.category == expected
    assert result.confidence in {"high", "medium", "low"}
    assert result.action


def test_classify_unknown_has_low_confidence():
    result = classify_failure(Failure(nodeid="x", test_name="y", message="weird failure"))
    assert result.category == "UNKNOWN"
    assert result.confidence == "low"


def test_parse_junit(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_XML, encoding="utf-8")

    failures = parse_junit(junit)

    assert len(failures) == 2
    assert failures[0].test_name == "test_create_order"
    assert "500" in failures[0].message
    assert failures[1].test_name == "test_get_product"


def test_render_markdown_contains_summary_and_rows(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_XML, encoding="utf-8")
    results = triage_failures(parse_junit(junit))

    report = render_markdown(results)
    assert "# 测试失败归因报告" in report
    assert "失败用例：2" in report
    assert "服务端 5xx" in report
    assert "环境/连接" in report
    assert "test_create_order" in report


def test_llm_disabled_without_env(monkeypatch):
    for name in ("TF_LLM_BASE_URL", "TF_LLM_API_KEY", "TF_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert LlmConfig.from_env() is None

    result = classify_failure(Failure(nodeid="x", test_name="y", message="assert 503 == 200"))
    assert enrich(result) is None


def test_cli_writes_report(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_XML, encoding="utf-8")
    out = tmp_path / "triage.md"

    code = main(["--junit", str(junit), "--out", str(out)])

    assert code == 0
    content = out.read_text(encoding="utf-8")
    assert "失败用例：2" in content
    assert "test_get_product" in content


def test_cli_missing_junit(tmp_path, capsys):
    code = main(["--junit", str(tmp_path / "none.xml"), "--out", str(tmp_path / "o.md")])
    assert code == 2
    assert "未找到" in capsys.readouterr().err
