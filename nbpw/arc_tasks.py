"""Small ARC-style grid tasks (not full ARC-AGI)."""

def _flip_h(g): return [row[::-1] for row in g]
def _flip_v(g): return g[::-1]
def _rot90(g): return [list(r) for r in zip(*g[::-1])]
def _rot180(g): return [row[::-1] for row in g[::-1]]
def _transpose(g): return [list(r) for r in zip(*g)]

TASKS = [
    {"id": "flip_h", "input": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "output": _flip_h([[1, 0, 0], [0, 1, 0], [0, 0, 1]])},
    {"id": "flip_v", "input": [[1, 0, 0], [0, 1, 0], [0, 0, 2]], "output": _flip_v([[1, 0, 0], [0, 1, 0], [0, 0, 2]])},
    {"id": "rot90", "input": [[1, 0, 0], [0, 1, 0], [0, 0, 2]], "output": _rot90([[1, 0, 0], [0, 1, 0], [0, 0, 2]])},
    {"id": "rot180", "input": [[1, 0, 0], [0, 1, 0], [0, 0, 2]], "output": _rot180([[1, 0, 0], [0, 1, 0], [0, 0, 2]])},
    {"id": "transpose", "input": [[1, 2, 3], [0, 1, 0], [0, 0, 2]], "output": _transpose([[1, 2, 3], [0, 1, 0], [0, 0, 2]])},
    {"id": "color_map", "input": [[1, 2], [2, 1]], "output": [[2, 3], [3, 2]]},
    {"id": "tile2", "input": [[1, 2], [3, 4]], "output": [[1, 2, 1, 2], [3, 4, 3, 4], [1, 2, 1, 2], [3, 4, 3, 4]]},
    {"id": "crop", "input": [[0, 0, 0, 0], [0, 5, 5, 0], [0, 5, 5, 0], [0, 0, 0, 0]], "output": [[5, 5], [5, 5]]},
    {"id": "border", "input": [[1]], "output": [[4, 4, 4], [4, 1, 4], [4, 4, 4]]},
    {"id": "count", "input": [[1, 0], [0, 1], [1, 1]], "output": [[4]]},
    {"id": "translate", "input": [[1, 0, 0], [1, 0, 0], [1, 0, 0]], "output": [[0, 1, 0], [0, 1, 0], [0, 1, 0]]},
    {"id": "mirror", "input": [[1, 2, 3], [4, 5, 6]], "output": [[1, 2, 3, 3, 2, 1], [4, 5, 6, 6, 5, 4]]},
]
