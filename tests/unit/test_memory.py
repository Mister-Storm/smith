def test_start_session(memory_service):
    session_id = memory_service.start_session()
    assert session_id
    assert len(session_id) == 36


def test_add_and_get_messages(memory_service):
    session_id = memory_service.start_session()
    memory_service.add_message(session_id, "user", "hello")
    memory_service.add_message(session_id, "assistant", "hi there")

    messages = memory_service.get_recent_messages(session_id)
    assert messages == [("user", "hello"), ("assistant", "hi there")]


def test_get_recent_messages_limit(memory_service):
    session_id = memory_service.start_session()
    for i in range(5):
        memory_service.add_message(session_id, "user", f"msg {i}")

    messages = memory_service.get_recent_messages(session_id, limit=3)
    assert len(messages) == 3
    assert messages[0] == ("user", "msg 2")


def test_count_conversations(memory_service):
    session_a = memory_service.start_session()
    session_b = memory_service.start_session()
    memory_service.add_message(session_a, "user", "a")
    memory_service.add_message(session_b, "user", "b")
    memory_service.add_message(session_b, "assistant", "reply")

    assert memory_service.count_conversations() == 3


def test_session_isolation(memory_service):
    session_a = memory_service.start_session()
    session_b = memory_service.start_session()
    memory_service.add_message(session_a, "user", "only a")

    assert memory_service.get_recent_messages(session_a) == [("user", "only a")]
    assert memory_service.get_recent_messages(session_b) == []
