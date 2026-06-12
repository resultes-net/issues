import os

def test_answer_exists():
    assert os.path.exists("answer.txt")

def test_answer_not_empty():
    with open("answer.txt", "r") as f:
        content = f.read()
        assert len(content) > 0

if __name__ == "__main__":
    test_answer_exists()
    test_answer_not_empty()
    print("Tests passed!")
