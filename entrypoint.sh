#!/bin/bash
set -e

# Generate the kubeconfig if AWS credentials and cluster details are available
if [ -n "ap-south-1" ] && [ -n "$EKS_CLUSTER_NAME" ]; then
    echo "Initializing EKS Kubeconfig for cluster: $EKS_CLUSTER_NAME in ap-south-1..."
    aws eks update-kubeconfig --region "ap-south-1" --name "$EKS_CLUSTER_NAME"
else
    echo "No AWS_REGION or EKS_CLUSTER_NAME provided. Skipping kubeconfig generation."
    echo "Fallback to default IAM Role or KUBECONFIG if mounted."
fi

# Execute the main application
echo "Starting application with arguments: $@"
exec python main.py "$@"
