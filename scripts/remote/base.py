"""Boilerplate for all jobs."""
from mrjob.job import MRJob


def job(sc, input_path):
    return False


class JobRunner(MRJob):
    def spark(self, input_path, output_path):
        """Setup context and write result to file."""
        from pyspark import SparkContext
        import sys
        import s3fs

        sc = SparkContext(appName="REPLACE_NAME")
        s3 = s3fs.S3FileSystem()

        # Setup PYTHONPATH correctly for job.
        sys.path.append("quant")
        result = job(sc, input_path)

        # Output job result to S3 (using `s3fs` for filesystem semantics).
        with s3.open(output_path, "w") as output_file:
            print(result, file=output_file)
        sc.stop()


if __name__ == "__main__":
    JobRunner.run()
