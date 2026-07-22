from server.rooms.codes import _ALPHABET, _CODE_LENGTH, generate_room_code


def test_generated_code_has_expected_length_and_alphabet():
    code = generate_room_code(lambda _c: False)
    assert len(code) == _CODE_LENGTH
    assert all(ch in _ALPHABET for ch in code)


def test_retries_on_a_collision():
    calls = []

    def exists(code: str) -> bool:
        calls.append(code)
        return len(calls) == 1  # first generated code collides, second doesn't

    code = generate_room_code(exists)
    assert len(calls) == 2
    assert code == calls[1]
