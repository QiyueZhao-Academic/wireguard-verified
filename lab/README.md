# Network laboratory (Linux only)

**Status: provided, not exercised.** No measurement from this directory
appears in the report, and none should be inferred. See `docs/limitations.md`.

## Why it cannot run on macOS

`ip netns` is a Linux kernel interface. XNU has no equivalent: macOS offers
`pf`, `ifconfig` and `utun` interfaces, but no namespace-level isolation of
the network stack. Running this topology requires a Linux kernel.

```sh
brew install lima
limactl start --name=wg template://ubuntu-lts
limactl shell wg
```

Inside the VM:

```sh
sudo apt-get install -y wireguard-tools tcpdump iproute2
cd /path/to/wireguard-verified
sudo lab/topology.sh
```

## Topology

```
  ns-alice                 ns-router                  ns-bob
 ┌────────┐              ┌───────────┐              ┌────────┐
 │ veth-a │══════════════│ veth-ra   │              │        │
 │10.0.0.2│  10.0.0.0/24 │ 10.0.0.1  │              │        │
 │        │              │           │ 10.0.1.0/24  │ veth-b │
 │  wg0   │              │ veth-rb   │══════════════│10.0.1.2│
 │10.9.0.1│              │ 10.0.1.1  │              │  wg0   │
 └────────┘              └───────────┘              │10.9.0.2│
                                                    └────────┘
```

`ns-router` sits on every path and carries `tc netem` for injected delay,
jitter, loss and reordering. The three namespaces use non-overlapping ranges
so that direction is legible at a glance in a capture.

`topology.sh` is idempotent: re-running it tears down and rebuilds rather than
leaving residue.

## What this layer would contribute

The correspondence table in `docs/wire-to-model.md` is currently checked
against the specification and the model sources. With captures, each row could
additionally be checked against actual bytes on the wire, which would close
the loop between the artifact and the models. That is the intended next step
and is stated as future work rather than as a result.
