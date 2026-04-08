# tests/test_identity.py
# ============================================================
# Identity Layer Test Suite
# Run: pytest tests/test_identity.py -v
# ============================================================

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from identity.persona import get_persona
from identity.prompt_builder import build_system_prompt, detect_language


class TestPersona:

    def test_persona_loads(self):
        persona = get_persona()
        assert persona is not None

    def test_persona_has_name(self):
        persona = get_persona()
        assert hasattr(persona, "name")
        assert persona.name == "Aria"

    def test_persona_has_company(self):
        persona = get_persona()
        assert hasattr(persona, "company")
        assert len(persona.company) > 0

    def test_persona_has_role(self):
        persona = get_persona()
        assert hasattr(persona, "role")

    def test_persona_has_greeting(self):
        persona = get_persona()
        assert hasattr(persona, "hindi_greeting")
        assert len(persona.hindi_greeting) > 0


class TestLanguageDetection:

    def test_hindi_detected(self):
        assert detect_language("Mera AC thanda nahi kar raha") == "hindi"

    def test_english_detected(self):
        assert detect_language("My AC is not working") == "english"

    def test_hindi_common_words(self):
        assert detect_language("kya aap meri madad kar sakte hain") == "hindi"

    def test_greeting_hindi(self):
        assert detect_language("namaste") == "hindi"


class TestPromptBuilder:

    def test_prompt_builds_without_error(self):
        persona = get_persona()
        prompt  = build_system_prompt(persona=persona, mode="general")
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_prompt_contains_name(self):
        persona = get_persona()
        prompt  = build_system_prompt(persona=persona, mode="general")
        assert "Aria" in prompt

    def test_prompt_changes_with_mode(self):
        persona       = get_persona()
        sales_prompt  = build_system_prompt(persona=persona, mode="sales")
        support_prompt = build_system_prompt(persona=persona, mode="support")
        assert sales_prompt != support_prompt

    def test_context_injected_in_prompt(self):
        persona = get_persona()
        context = "Customer previously complained about noise"
        prompt  = build_system_prompt(
            persona=persona, mode="support", context=context
        )
        assert context in prompt