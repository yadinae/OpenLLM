"""CLI bind 函数边界条件测试"""
from __future__ import annotations

from unittest import mock


from openllm.cli.binder import bind_agent, BINDERS


class TestBinder:
    def test_unknown_agent(self):
        result = bind_agent("nonexistent")
        assert "Unknown agent" in result
        assert "aider" in result  # 应该列出支持的工具

    def test_supported_agents(self):
        for agent in ["aider", "continue", "hermes", "openclaw", "claude-code"]:
            assert agent in BINDERS

    def test_bind_aider(self):
        """验证 aider 配置生成"""
        binder = BINDERS["aider"]
        assert "openllm-api-key" in binder["config"]
        assert "http://{host}:{port}" in binder["config"]

    def test_bind_continue(self):
        """验证 continue 配置生成"""
        binder = BINDERS["continue"]
        assert "apiBase" in binder["config"]
        assert "{host}:{port}" in binder["config"]

    @mock.patch("openllm.cli.binder.os.path.exists", return_value=False)
    @mock.patch("openllm.cli.binder.Path.write_text")
    @mock.patch("openllm.cli.binder.Path.mkdir")
    def test_bind_creates_file(self, mock_mkdir, mock_write, mock_exists):
        result = bind_agent("aider", host="0.0.0.0", port=8080)
        assert "Configured" in result
        assert "0.0.0.0:8080" in result

    @mock.patch("openllm.cli.binder.os.path.exists", return_value=True)
    @mock.patch("openllm.cli.binder.Path.read_text", return_value="some config with OpenLLM in it")
    def test_bind_already_configured(self, mock_read, mock_exists):
        result = bind_agent("aider")
        assert "already configured" in result

    @mock.patch("openllm.cli.binder.os.path.exists", return_value=True)
    @mock.patch("openllm.cli.binder.Path.read_text", return_value="some config without reference")
    @mock.patch("openllm.cli.binder.Path.write_text")
    @mock.patch("openllm.cli.binder.Path.mkdir")
    def test_bind_overwrites_existing_file(self, mock_mkdir, mock_write, mock_read, mock_exists):
        """P2: 已有文件但没有 openllm 配置时，静默覆写"""
        bind_agent("aider")
        # 由于没有匹配 "openllm"，它应该覆写文件
        mock_write.assert_called_once()

    def test_hermes_returns_instruction_not_config(self):
        """hermes 没有 config 模板，返回 instruction"""
        result = bind_agent("hermes", host="127.0.0.1", port=11343)
        assert "Add to ~/.hermes/config.yaml" in result
