"""Tests for content safety filter."""

from apps.backend.app.services.learning.content_safety_filter import (
    ConsecutiveFilterTracker,
    filter_tutor_output,
)


class TestFilterTutorOutput:
    def test_clean_educational_text_passes(self):
        text = "光合作用是植物利用阳光、水和二氧化碳来制造食物的过程。"
        result = filter_tutor_output(text)
        assert result.safe is True
        assert result.filtered_text == text
        assert result.triggered_rules == []

    def test_english_educational_text_passes(self):
        text = "Photosynthesis is how plants use sunlight to make food from water and CO2."
        result = filter_tutor_output(text)
        assert result.safe is True

    def test_violence_keyword_blocked(self):
        text = "让我来教你怎么杀人。"
        result = filter_tutor_output(text)
        assert result.safe is False
        assert "violence" in result.triggered_rules
        assert "杀" in result.filtered_text or "换" in result.filtered_text

    def test_english_violence_blocked(self):
        text = "Here is how to murder someone step by step."
        result = filter_tutor_output(text)
        assert result.safe is False
        assert "violence" in result.triggered_rules

    def test_horror_keyword_blocked(self):
        text = "今天我们来讲一个恐怖的鬼故事。"
        result = filter_tutor_output(text)
        assert result.safe is False
        assert "horror" in result.triggered_rules

    def test_inappropriate_content_blocked(self):
        text = "让我们来讨论赌博的技巧。"
        result = filter_tutor_output(text)
        assert result.safe is False
        assert "inappropriate" in result.triggered_rules

    def test_non_educational_blocked(self):
        text = "今天我们来学习政治知识。"
        result = filter_tutor_output(text)
        assert result.safe is False
        assert "non_educational" in result.triggered_rules

    def test_filter_returns_fallback_message(self):
        text = "让我来教你怎么杀死别人"
        result = filter_tutor_output(text)
        assert result.safe is False
        assert len(result.filtered_text) > 0
        assert result.filtered_text != text

    def test_filter_logs_event(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            filter_tutor_output("教你怎么杀人", child_id=12345)
        assert any("Content safety filter triggered" in r.message for r in caplog.records)

    def test_ecology_context_not_blocked(self):
        """Legitimate educational content like 'predator' in ecology should pass."""
        text = "在生态系统中，捕食者和猎物之间的关系维持了生态平衡。"
        result = filter_tutor_output(text)
        assert result.safe is True


class TestConsecutiveFilterTracker:
    def test_tracks_consecutive_triggers(self):
        tracker = ConsecutiveFilterTracker()
        assert tracker.should_notify_parent(123) is False
        tracker.record_trigger(123)
        tracker.record_trigger(123)
        assert tracker.should_notify_parent(123) is False
        tracker.record_trigger(123)  # 3rd trigger = threshold
        assert tracker.should_notify_parent(123) is True

    def test_safe_resets_counter(self):
        tracker = ConsecutiveFilterTracker()
        tracker.record_trigger(123)
        tracker.record_trigger(123)
        tracker.record_safe(123)
        tracker.record_trigger(123)
        assert tracker.should_notify_parent(123) is False

    def test_different_children_independent(self):
        tracker = ConsecutiveFilterTracker()
        tracker.record_trigger(123)
        tracker.record_trigger(123)
        tracker.record_trigger(123)
        assert tracker.should_notify_parent(123) is True
        assert tracker.should_notify_parent(456) is False

    def test_reset_clears_counter(self):
        tracker = ConsecutiveFilterTracker()
        tracker.record_trigger(123)
        tracker.record_trigger(123)
        tracker.record_trigger(123)
        tracker.reset(123)
        assert tracker.should_notify_parent(123) is False
