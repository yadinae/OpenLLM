"""
Prompt Enhancer — 统一系统提示增强器

整合 Code Thinking 和 Terse Mode 两种增强策略。

在 chat completions 请求流程中注入：
1. 自动检测任务类型 → 注入代码思维（可选）
2. 根据请求参数 → 注入简洁模式（可选）
3. 保持与现有 token optimizer 的兼容性
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.code_thinking import CodeThinkingInjector, get_injector as get_ct_injector
from src.terse_mode import TerseModeInjector, get_injector as get_terse_injector

logger = logging.getLogger(__name__)


@dataclass
class EnhanceResult:
    """增强结果"""
    messages: list[dict]
    code_thinking_enabled: bool
    terse_mode_enabled: bool
    terse_intensity: str = ""
    original_message_count: int = 0
    enhanced_message_count: int = 0


class PromptEnhancer:
    """统一提示增强器

    在请求进入模型之前，智能注入系统提示。
    """

    def __init__(
        self,
        code_thinking_auto: bool = True,
        code_thinking_language: str = "en",
        terse_enabled: bool = False,
        terse_intensity: str = "moderate",
        terse_language: str = "en",
    ):
        self.ct_injector = CodeThinkingInjector(
            auto_enable=code_thinking_auto,
            language=code_thinking_language,
        )
        self.terse_injector = TerseModeInjector(
            enabled=terse_enabled,
            intensity=terse_intensity,
            language=terse_language,
        )

    def enhance(
        self,
        messages: list[dict],
        enable_code_thinking: Optional[bool] = None,
        enable_terse: Optional[bool] = None,
        terse_intensity: Optional[str] = None,
    ) -> EnhanceResult:
        """增强消息

        Args:
            messages: 原始消息列表
            enable_code_thinking: 是否启用代码思维（None = 自动检测）
            enable_terse: 是否启用简洁模式（None = 使用默认配置）
            terse_intensity: 简洁强度（None = 使用默认配置）

        Returns:
            EnhanceResult
        """
        enhanced = messages
        ct_enabled = False
        terse_enabled_final = False
        terse_intensity_final = ""

        # 1. Code Thinking
        if enable_code_thinking is True:
            # 强制启用
            enhanced, ct_enabled = self.ct_injector.inject(enhanced, force=True)
        elif enable_code_thinking is None:
            # 自动检测
            enhanced, ct_enabled = self.ct_injector.inject(enhanced, force=False)
        # else: False = 不启用

        # 2. Terse Mode
        if enable_terse is not None:
            if terse_intensity:
                self.terse_injector.set_intensity(terse_intensity)

            if enable_terse:
                enhanced, terse_enabled_final = self.terse_injector.inject(enhanced, force=True)
                terse_intensity_final = self.terse_injector.intensity
        elif self.terse_injector.enabled:
            enhanced, terse_enabled_final = self.terse_injector.inject(enhanced, force=False)
            terse_intensity_final = self.terse_injector.intensity

        if ct_enabled or terse_enabled_final:
            logger.info(
                f"Prompt enhanced: code_thinking={ct_enabled}, "
                f"terse={terse_enabled_final} ({terse_intensity_final})"
            )

        return EnhanceResult(
            messages=enhanced,
            code_thinking_enabled=ct_enabled,
            terse_mode_enabled=terse_enabled_final,
            terse_intensity=terse_intensity_final,
            original_message_count=len(messages),
            enhanced_message_count=len(enhanced),
        )


# ============================================================
# Global instance
# ============================================================

_enhancer: Optional[PromptEnhancer] = None


def get_enhancer(config: Optional[dict] = None) -> PromptEnhancer:
    """获取全局增强器实例"""
    global _enhancer
    if _enhancer is None:
        cfg = config or {}
        _enhancer = PromptEnhancer(
            code_thinking_auto=cfg.get("code_thinking_auto", True),
            code_thinking_language=cfg.get("code_thinking_language", "en"),
            terse_enabled=cfg.get("terse_enabled", False),
            terse_intensity=cfg.get("terse_intensity", "moderate"),
            terse_language=cfg.get("terse_language", "en"),
        )
    return _enhancer


def reset_enhancer():
    global _enhancer
    _enhancer = None
