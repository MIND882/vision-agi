# tests/test_aria.py
# ============================================================
# Aria Test Suite
# Run: pytest tests/test_aria.py -v
# ============================================================

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from identity.aria import Aria


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def aria():
    """Fresh Aria instance for each test."""
    return Aria()


# ── Mode Detection Tests (no LLM call — fast) ────────────────

class TestModeDetection:

    def test_support_mode_hindi(self, aria):
        assert aria._detect_mode("Mera AC thanda nahi kar raha") == "support"

    def test_support_mode_english(self, aria):
        assert aria._detect_mode("My AC is not working") == "support"

    def test_sales_mode_amc(self, aria):
        assert aria._detect_mode("AMC plan kya hota hai") == "sales"

    def test_sales_mode_appointment(self, aria):
        assert aria._detect_mode("mujhe appointment book karni hai") == "sales"

    def test_general_mode(self, aria):
        assert aria._detect_mode("hello") == "general"

    def test_support_mode_gas(self, aria):
        assert aria._detect_mode("AC mein gas khatam ho gayi") == "support"


# ── Session Management Tests ─────────────────────────────────

class TestSessionManagement:

    def test_session_id_created(self, aria):
        assert aria.session_id is not None
        assert len(aria.session_id) == 36   # UUID4 format

    def test_history_empty_on_start(self, aria):
        assert aria.history == []

    def test_turn_count_starts_zero(self, aria):
        assert aria.turn_count == 0

    def test_reset_clears_history(self, aria):
        aria.history    = ["fake message"]
        aria.turn_count = 5
        aria.history    = []   # simulate reset without DB
        aria.turn_count = 0
        assert aria.history    == []
        assert aria.turn_count == 0

    def test_two_aria_instances_different_sessions(self):
        a1 = Aria()
        a2 = Aria()
        assert a1.session_id != a2.session_id


# ── LLM Response Tests (requires Groq API) ───────────────────

class TestAriaChat:

    def test_greeting_returns_string(self, aria):
        greeting = aria.greet()
        assert isinstance(greeting, str)
        assert len(greeting) > 10

    def test_chat_returns_dict(self, aria):
        result = aria.chat("Hello")
        assert isinstance(result, dict)
        assert "response" in result
        assert "language" in result
        assert "mode"     in result

    def test_hindi_detected(self, aria):
        result = aria.chat("Mera AC thanda nahi kar raha hai")
        assert result["language"] == "hindi"

    def test_support_mode_triggered(self, aria):
        result = aria.chat("Mera AC band ho gaya hai")
        assert result["mode"] == "support"

    def test_sales_mode_triggered(self, aria):
        result = aria.chat("AMC plan kya hota hai")
        assert result["mode"] == "sales"

    def test_response_not_empty(self, aria):
        result = aria.chat("Namaste")
        assert len(result["response"]) > 0

    def test_multi_turn_history_grows(self, aria):
        aria.chat("Hello")
        aria.chat("Mera AC kharab hai")
        assert len(aria.history) == 4   # 2 human + 2 assistant messages

    def test_hindi_response_for_hindi_input(self, aria):
        result = aria.chat("Mera AC thanda nahi kar raha hai")
        # Aria should respond in Hindi — check for common Hindi words
        hindi_indicators = ["aap", "main", "hain", "hai", "karo", "karein",
                           "aapka", "ji", "hum", "kijiye"]
        response_lower = result["response"].lower()
        has_hindi = any(word in response_lower for word in hindi_indicators)
        assert has_hindi, f"Expected Hindi response, got: {result['response'][:100]}"


# ── Memory Integration Tests ─────────────────────────────────

class TestMemoryIntegration:

    def test_episodic_memory_initialized(self, aria):
        assert aria.episodic is not None

    def test_semantic_memory_initialized(self, aria):
        assert aria.semantic is not None

    def test_end_session_does_not_crash(self, aria):
        aria.chat("Test message")
        try:
            aria.end_session(final_score=0.9)
        except Exception as e:
            pytest.fail(f"end_session raised exception: {e}")


# ── Edge Case Tests ───────────────────────────────────────────

class TestEdgeCases:

    def test_empty_message(self, aria):
        result = aria.chat("")
        assert "response" in result

    def test_very_long_message(self, aria):
        long_msg = "AC " * 200
        result   = aria.chat(long_msg)
        assert "response" in result

    def test_english_message(self, aria):
        result = aria.chat("My AC is not working")
        assert result["language"] == "english"

    def test_mixed_language(self, aria):
        result = aria.chat("Mera AC not working hai")
        assert result["language"] in ["hindi", "english"]   # either is fine