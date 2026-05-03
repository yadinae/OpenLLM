"""
Terse Mode — 输出压缩（洞穴人风格）

Inspired by context-mode's "Output Compression" — Terse like caveman.

核心理念：
- 去掉废话、客套、修饰（filler, pleasantries, hedging）
- 技术内容精确不变
- 片段式表达 OK，用短同义词
- 安全警告和不可逆操作自动扩展
- 节省 65-75% output tokens

使用方式：
- 在 system prompt 中注入 terse 指令
- 可手动启用或通过请求参数启用
- 可配置强度（mild/moderate/extreme）

典型效果：
Before: "Sure! I'd be happy to help you with that. Let me take a look at the file and see what we can do to improve it..."
After:  "Checked file. Issue: missing import. Fix: add `import os` at line 1."
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Terse prompt templates by intensity
# ============================================================

TERSE_MILD = """\
## Communication Style

Be concise and direct. Skip pleasantries, filler words, and hedging.
- No "Sure!", "I'd be happy to help", "Let me take a look"
- Get straight to the point
- Keep explanations brief but complete
- Use bullet points for lists\
"""

TERSE_MODERATE = """\
## Communication Style — Terse Mode

Write like a caveman. Technical substance exact. Only fluff dies.

Rules:
- Drop articles (a, an, the), filler words (just, really, basically), pleasantries, hedging
- Fragments OK. Short synonyms OK.
- Code unchanged — never compress code
- Pattern: [thing] [action] [reason]. [next step].
- Example: "Fixed null ref in user.service. Added null check before access. Tests pass."

Auto-expand for:
- Security warnings
- Irreversible actions (delete, drop, rm -rf)
- User confusion\
"""

TERSE_EXTREME = """\
## Communication Style — Maximum Compression

Caveman speak. Zero fluff. Technical precision 100%.

Rules:
- NO articles, filler, pleasantries, hedging, explanations unless asked
- Fragments always OK
- Code unchanged
- Pattern: [thing] → [action] → [reason]
- Use arrows, dashes, symbols instead of words
- Numbers > words ("3 errors" not "three errors were found")

Examples:
- ❌ "I found three errors in the file. The first one is a missing semicolon..."
- ✅ "3 errors: L5 missing `;`, L12 unused import, L45 type mismatch"
- ❌ "Would you like me to fix these? I can also add some tests..."
- ✅ "Fix 3 errors? Add tests? Y/N"

Auto-expand for security, destructive actions, user confusion.\
"""

# 中文版
TERSE_MODERATE_CN = """\
## 沟通风格 — 简洁模式

像洞穴人一样说话。技术内容精确，废话全删。

规则：
- 去掉冠词、废话（"当然"、"我很乐意"、"让我看看"）、修饰词
- 片段 OK，短同义词 OK
- 代码不变 —— 绝不压缩代码
- 模式：[对象] [动作] [原因]。[下一步]。
- 示例："修了空引用。user.service 加 null 检查。测试通过。"

自动扩展：安全警告、不可逆操作、用户困惑时\
"""


# ============================================================
# TerseModeInjector
# ============================================================

class TerseModeInjector:
    """Terse 模式注入器

    根据配置的强度注入系统提示，压缩模型输出。
    """

    INTENSITY_LEVELS = {
        "mild": {
            "en": TERSE_MILD,
            "zh": TERSE_MILD,  # mild 不区分中英文
        },
        "moderate": {
            "en": TERSE_MODERATE,
            "zh": TERSE_MODERATE_CN,
        },
        "extreme": {
            "en": TERSE_EXTREME,
            "zh": TERSE_EXTREME,
        },
    }

    def __init__(
        self,
        enabled: bool = False,
        intensity: str = "moderate",
        language: str = "en",
    ):
        self.enabled = enabled
        self.intensity = intensity if intensity in self.INTENSITY_LEVELS else "moderate"
        self.language = language
        self.system_prompt = self.INTENSITY_LEVELS[self.intensity].get(
            language, self.INTENSITY_LEVELS[self.intensity]["en"]
        )

    def set_intensity(self, intensity: str):
        """设置简洁强度"""
        if intensity in self.INTENSITY_LEVELS:
            self.intensity = intensity
            self.system_prompt = self.INTENSITY_LEVELS[intensity].get(
                self.language, self.INTENSITY_LEVELS[intensity]["en"]
            )

    def inject(self, messages: list[dict], force: bool = False) -> tuple[list[dict], bool]:
        """注入 terse 模式系统提示

        Args:
            messages: 消息列表
            force: 是否强制注入

        Returns:
            (增强后的消息列表, 是否注入了提示)
        """
        if not self.enabled and not force:
            return messages, False

        # 检查是否已经有 terse 提示
        for msg in messages:
            content = msg.get("content", "")
            if "Terse Mode" in content or "洞穴人" in content or "Communication Style" in content:
                return messages, False

        injection = "\n\n" + self.system_prompt

        # 注入到 system message
        enhanced = []
        injected = False
        for msg in messages:
            if msg.get("role") == "system" and not injected:
                enhanced.append({
                    "role": "system",
                    "content": msg.get("content", "") + injection,
                })
                injected = True
            else:
                enhanced.append(msg)

        if not injected:
            enhanced.insert(0, {
                "role": "system",
                "content": self.system_prompt,
            })
            injected = True

        logger.info(f"Terse mode enabled (intensity={self.intensity})")
        return enhanced, injected

    def get_prompt(self) -> str:
        return self.system_prompt


# ============================================================
# Global instance
# ============================================================

_injector: Optional[TerseModeInjector] = None


def get_injector(
    enabled: bool = False,
    intensity: str = "moderate",
    language: str = "en",
) -> TerseModeInjector:
    """获取全局 terse 注入器"""
    global _injector
    if _injector is None:
        _injector = TerseModeInjector(
            enabled=enabled,
            intensity=intensity,
            language=language,
        )
    return _injector


def reset_injector():
    global _injector
    _injector = None
