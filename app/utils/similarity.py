import numpy as np


def cosine(a, b) -> float:
    """Cosine similarity, returning 0.0 for degenerate (empty/zero-norm)
    vectors instead of raising -- happens when an embedding call failed and
    returned an empty list.
    """
    if a is None or b is None or len(a) == 0 or len(b) == 0:
        return 0.0
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))
