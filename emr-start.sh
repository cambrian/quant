#!/bin/bash
# TODO: Remove me.
set -e

if [ "$#" -ne 1 ]; then
  echo "Expected a single argument (relative repo path for the script to run)." >&2
  exit 1
fi

CLUSTER_NAME="OptimizerCluster"
DEPENDENCY_INSTALL_SCRIPT=emr-bootstrap.sh
CLUSTER_CONFIG=emr-config.json

echo "Uploading dependency install script and cluster configuration to S3..."
aws s3 cp $DEPENDENCY_INSTALL_SCRIPT s3://cambrian-quant-test/
aws s3 cp $CLUSTER_CONFIG s3://cambrian-quant-test/

echo "Creating cluster on EMR..."
# Create compute cluster on EMR.
aws emr create-cluster \
    --name $CLUSTER_NAME \
    --instance-type m4.large \
    --use-default-roles \
    # Desired number of worker nodes + 1 (for the master node).
    --instance-count 4 \
    --auto-terminate \
    --release-label emr-5.23.0 \
    --configurations s3://cambrian-quant-test/$CLUSTER_CONFIG \
    --bootstrap-actions \
        Path=s3://cambrian-quant-test/$DEPENDENCY_INSTALL_SCRIPT,Args=,Name=bootstrap \
    --applications Name=Hive,Pig,Hue,Spark,Livy

aws emr add-steps --cluster-id j-2AXXXXXXGAPLF --steps \
    Name="Command Runner",Jar="command-runner.jar",Args=["spark-submit",home/hadoop/quant/$1.py]
