def job(sc, input_path):
    from research.util.optimizer import BasicGridSearch, optimize

    # Vertex at (3, -2, 3).
    def paraboloid(a, b):
        return -1 * ((a - 3) ** 2 + (b + 2) ** 2) + 3

    param_spaces = {"a": range(-100, 100, 1), "b": range(-50, 50, 1)}
    return optimize(sc, BasicGridSearch, paraboloid, param_spaces, parallelism=2)
