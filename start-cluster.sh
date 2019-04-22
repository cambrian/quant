CLUSTERNAME="SimCluster"
DEPENDENCY_INSTALL_SCRIPT=emr-install-deps.sh
CLUSTER_CONFIG=emr-cluster-config.json

echo "Uploading dependency install script and cluster configuration to S3..."
aws s3 cp $DEPENDENCY_INSTALL_SCRIPT s3://cambrian-quant-test/
aws s3 cp $CLUSTER_CONFIG s3://cambrian-quant-test/

echo "Creating cluster on EMR..."
# Create compute cluster on EMR
aws emr create-cluster \
    --name $CLUSTERNAME \
    --instance-type m4.large \
    --use-default-roles \
    # Desired number of worker nodes + 1 (for the master node)
    --instance-count 4 \
    --auto-terminate \
    --release-label emr-5.23.0 \
    --configurations file://$CLUSTER_CONFIG \
    --bootstrap-actions \
        Path=s3://cambrian-quant-test/$DEPENDENCY_INSTALL_SCRIPT,Args=,Name=install-deps \
    --applications Name=Spark