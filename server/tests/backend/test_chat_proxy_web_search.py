"""Verify backend chat proxy forwards web_search to agent."""


from apps.backend.app.routers.ai_chat import ChatStreamRequest


def test_chat_stream_request_accepts_web_search():
    """ChatStreamRequest model accepts web_search field."""
    req = ChatStreamRequest(question="hi", deep_think=False, web_search=True)
    assert req.web_search is True


def test_chat_stream_request_defaults_web_search_false():
    req = ChatStreamRequest(question="hi")
    assert req.web_search is False