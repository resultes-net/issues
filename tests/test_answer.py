import os

def test_answer_contains_requirements():
    with open("answer.txt", "r") as f:
        content = f.read()
        # Check for key requirements in the answer
        assert "Relative/DT Mode" in content
        assert "Absolute Mode" in content
        assert "DT boiler-demand" in content
        assert "DT heat pump-boiler" in content
        assert "DT maximum storage temperature-heat pump" in content
        assert "DT collector-maximum storage temperature" in content
        assert "default: 0K" in content
        assert "default: 5K" in content
        assert "default: 15K" in content
        assert "converted to maintain the current setpoints" in content

def test_answer_exists():
    assert os.path.exists("answer.txt")

def test_answer_not_empty():
    with open("answer.txt", "r") as f:
        content = f.read()
        assert len(content) > 0

if __name__ == "__main__":
    test_answer_exists()
    test_answer_not_empty()
    test_answer_contains_requirements()
    print("Tests passed!")
