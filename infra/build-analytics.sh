#!/usr/bin/env bash
set -euo pipefail
cd /home/colton/Projects/Galapagos
export DOCKER_HOST=unix:///run/user/1000/galapagos-docker.sock
export PATH=/home/colton/Projects/Galapagos/tools/bin:/usr/bin
export DOCKER_BUILDKIT=0
docker build -f Dockerfile.regions -t galapagos-analytics:v1 .
kind load docker-image galapagos-analytics:v1 --name galapagos --nodes galapagos-control-plane
