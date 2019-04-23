# quant
Quantitative trading for cryptocurrencies.

## Setup
Run `./setup.sh`.

## Testing
Run `./dev.sh` to watch changes and re-run tests (any function prefixed with `test_`). To run
doctests, ensure you have the VS Code extensions installed, then type `CMD-Shift-T`.

Tests are only intended for the `trader` directory.

## Spark
For compute-intensive tasks (like hyperparameter searches), you might prefer to run a Spark job in
the cloud. To write your job, follow the pattern in `scripts/remote/paraboloid.py` (exporting a
single function `job` that encapsulates your task).

Sanity check your job by running `./local.sh scripts/remote/paraboloid.py` from the repo root. When
you are convinced that your job can run to completion, replace `./local.sh` with `./spark.sh`.

### Hints
- You may also provide a second parameter, which is the local file path to read input from. The
  default input path is `/dev/null`.
- If you use the input path, it will get translated to an S3 path after upload. Consequently, you
  should use a filesystem reader compatible with S3, and you might get issues when running locally.
- If you want to change the Spark cluster settings, you will have to edit `mrjob.conf`. Be careful
  when doing so, as these changes can mess up the cloud environment and cause your job to fail in
  a cryptic manner. Reference [here](https://mrjob.readthedocs.io/en/latest/guides/emr-opts.html).
- By default (i.e. assuming no changes to `mrjob.conf`), the job library will attempt, for each new
  job, to re-use an AWS cluster with the same configuration. If a cluster is idle for 20 minutes, it
  will time out, and the next job to be created will spawn a new cluster.
- Default AWS credentials are provided in `./spark.sh`, so no CLI config should be necessary.
