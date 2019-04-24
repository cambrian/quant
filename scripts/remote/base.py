"""Boilerplate for all remote EMR jobs."""

from mrjob.job import MRJob


def job(sc, input_path, working_dir):
    """Replaced by actual job at runtime."""
    return False


class JobRunner(MRJob):
    def spark(self, input_path, output_path):
        import os
        import sys

        import s3fs
        from pyspark import SparkContext

        # Set up context and S3 filesystem adapter.
        sc = SparkContext(appName="REPLACE_NAME")
        s3 = s3fs.S3FileSystem()

        # Setup PYTHONPATH correctly for dependencies.
        sys.path.append("quant")

        # Run job and output to S3.
        result = job(sc, input_path, os.getcwd())
        with s3.open(output_path, "w") as output_file:
            print(result, file=output_file)
        sc.stop()


if __name__ == "__main__":
    JobRunner.run()
