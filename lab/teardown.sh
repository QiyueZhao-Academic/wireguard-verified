#!/usr/bin/env bash
# Remove the topology. Safe to run when nothing is up.
set -u
for n in ns-alice ns-router ns-bob; do ip netns del "$n" 2>/dev/null || true; done
echo "topology down"
