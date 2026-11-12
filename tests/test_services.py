from app.services import sample_evenly


def test_sample_evenly_empty():
    assert sample_evenly([], 5) == []


def test_sample_evenly_fewer_than_k():
    items = [1, 2, 3]
    assert sample_evenly(items, 5) == [1, 2, 3]


def test_sample_evenly_exact_k():
    items = [1, 2, 3, 4, 5]
    assert sample_evenly(items, 5) == [1, 2, 3, 4, 5]


def test_sample_evenly_subsamples_correctly():
    items = list(range(100))
    sampled = sample_evenly(items, 10)
    assert len(sampled) == 10
    # Must preserve start and end
    assert sampled[0] == 0
    assert sampled[-1] == 99
    # Must be monotonic
    for i in range(len(sampled) - 1):
        assert sampled[i] < sampled[i + 1]


def test_sample_evenly_edge_cases():
    assert sample_evenly([42], 5) == [42]
    assert sample_evenly([1, 2, 3], 1) == [1]
