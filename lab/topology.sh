#!/usr/bin/env bash
# Build the three-namespace topology. Idempotent: tears down first.
#
# Linux only -- see lab/README.md for why, and for how to get a Linux kernel
# on macOS. Requires root (CAP_NET_ADMIN) and iproute2.
set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
  echo "error: network namespaces are a Linux kernel interface." >&2
  echo "       macOS has no equivalent; see lab/README.md." >&2
  exit 1
fi
[ "$(id -u)" -eq 0 ] || { echo "error: run as root (needs CAP_NET_ADMIN)" >&2; exit 1; }

NS=(ns-alice ns-router ns-bob)

teardown() {
  for n in "${NS[@]}"; do ip netns del "$n" 2>/dev/null || true; done
}

teardown
for n in "${NS[@]}"; do ip netns add "$n"; done

# alice <-> router
ip link add veth-a type veth peer name veth-ra
ip link set veth-a  netns ns-alice
ip link set veth-ra netns ns-router
ip netns exec ns-alice  ip addr add 10.0.0.2/24 dev veth-a
ip netns exec ns-router ip addr add 10.0.0.1/24 dev veth-ra

# router <-> bob
ip link add veth-b type veth peer name veth-rb
ip link set veth-b  netns ns-bob
ip link set veth-rb netns ns-router
ip netns exec ns-bob    ip addr add 10.0.1.2/24 dev veth-b
ip netns exec ns-router ip addr add 10.0.1.1/24 dev veth-rb

for n in "${NS[@]}"; do ip netns exec "$n" ip link set lo up; done
ip netns exec ns-alice  ip link set veth-a  up
ip netns exec ns-bob    ip link set veth-b  up
ip netns exec ns-router ip link set veth-ra up
ip netns exec ns-router ip link set veth-rb up
ip netns exec ns-router sysctl -qw net.ipv4.ip_forward=1

ip netns exec ns-alice ip route add 10.0.1.0/24 via 10.0.0.1
ip netns exec ns-bob   ip route add 10.0.0.0/24 via 10.0.1.1

echo "topology up: ${NS[*]}"
echo "verify with: ip netns exec ns-alice ping -c1 10.0.1.2"
