import pytest
from src.tester import ModelTester, ModelTestResult, CAPABILITY_TESTS


def test_extract_model_size():
    tester = ModelTester(None)

    assert tester._extract_model_size("groq/llama-3.3-70b-versatile") == "70b"
    assert tester._extract_model_size("mistral/mistral-large-latest") == ""
    assert tester._extract_model_size("qwen-3-32b") == "32b"
    assert tester._extract_model_size("model-name") == ""


def test_capability_tests_exist():
    expected = ["coding", "math", "reasoning", "json"]
    assert list(CAPABILITY_TESTS.keys()) == expected


def test_model_tester_init():
    registry = object()
    tester = ModelTester(registry)

    assert tester.registry is registry


def test_model_test_result_defaults():
    result = ModelTestResult(model_name="test-model", available=True, response_time_ms=100)

    assert result.model_name == "test-model"
    assert result.available is True
    assert result.response_time_ms == 100
    assert result.capabilities == []
    assert result.languages == []
    assert result.rpm_limit == 0
    assert result.tpm_limit == 0
    assert result.max_context_length == 0


def test_resolve_env_var():
    import os

    tester = ModelTester(None)
    os.environ["TEST_API_KEY"] = "test-key-value"

    assert tester._resolve_env_var("${TEST_API_KEY}") == "test-key-value"
    assert tester._resolve_env_var("") == ""
    assert tester._resolve_env_var("plain-key") == "plain-key"


def test_resolve_env_var_not_set():
    tester = ModelTester(None)

    assert tester._resolve_env_var("${NONEXISTENT_VAR}") == ""
