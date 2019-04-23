from mrjob.job import MRJob

from research.util.optimizer import BasicGridSearch, optimize


class OptimizeParaboloid(MRJob):
    def spark(self, input_path, output_path):
        # Spark may not be available where script is launched.
        from pyspark import SparkContext

        # Vertex at (3, -2, 3).
        def paraboloid(a, b):
            return -1 * ((a - 3) ** 2 + (b + 2) ** 2) + 3

        sc = SparkContext(appName="paraboloid")
        param_spaces = {"a": range(-100, 100, 1), "b": range(-50, 50, 1)}
        result = optimize(sc, BasicGridSearch, paraboloid, param_spaces, parallelism=2)

        with open(output_path, "w") as output_file:
            print(result, file=output_file)
        sc.stop()


if __name__ == "__main__":
    OptimizeParaboloid.run()
