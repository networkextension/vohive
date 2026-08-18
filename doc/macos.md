# Running VoHive natively on macOS (no Linux VM)

VoHive was written for Linux (it discovers modems by scanning `/sys` + globbing
`ttyUSB*`, and talks to the AT port through a kernel `tty` device). macOS does
neither for a Quectel-class modem: it won't attach a `tty` driver to the module's
vendor-specific (USB class `0xFF`) AT interface, so there is no `/dev/tty*` to open,
and there is no `/sys` to scan.

This document describes how to run the `darwin/arm64` (and `amd64`) build against a
Quectel EG25 / EC25-family module (e.g. a DJI 4G module re-flashed to EC25 identity)
**without a VM**, by bridging the USB AT interface to a PTY.

## How it works

```
  modem USB (if2, bulk AT)  ⇄  eg25_pty_bridge.py (libusb)  ⇄  PTY  ⇄  VoHive serial layer
```

1. `scripts/macos/eg25_pty_bridge.py` claims the AT interface's bulk endpoints with
   libusb and shuttles bytes to/from a pseudo-terminal, exposing a stable symlink
   (default `eg25-at.pty`).
2. VoHive opens that PTY as its AT port. Because the port path can't come from the
   config file (the port fields are runtime-resolved), it is injected via the
   `VOHIVE_AT_PORT_<device_id>` environment variable, which also **skips the Linux
   hardware-discovery scan** (see `internal/device/atport_override.go`).

Everything else (SMS, eSIM, operator selection, …) runs through the normal AT backend.
QMI/MBIM data-plane features that depend on Linux netlink degrade gracefully.

## Prerequisites

```bash
brew install libusb
python3 -m venv .venv && ./.venv/bin/pip install pyusb
```

The module must already present an EC25-class USB identity (`2c7c:0125`). For a DJI
module still on its private `2ca3:4006` id, re-flash it once with
`AT+QCFG="usbcfg",0x2C7C,0x0125,1,1,1,1,1,0,0` + `AT+CFUN=1,1`.

## Run

```bash
# 1. Build the UI once and embed it (skip if you only need -backend-only)
( cd web && npm ci && npm run build ) && cp -R web/dist internal/web/dist

# 2. Build the binary
go build -o /tmp/vohive ./cmd/vohive

# 3. Start the PTY bridge (keep it running)
./.venv/bin/python scripts/macos/eg25_pty_bridge.py     # publishes ./eg25-at.pty

# 4. Start VoHive, pointing the device at the PTY
VOHIVE_AT_PORT_eg25="$PWD/eg25-at.pty" \
  ./tmp/vohive -c config/config-mac.yaml
```

Open <http://localhost:7575> (default `admin` / `admin`). `config/config-mac.yaml`
declares a single AT-only device with `id: eg25`.

### Bridging a different interface

`if2` and `if3` are both AT ports on the EG25. The bridge uses `if2` by default; pass
`--iface 3` to use the spare (handy for manual `AT` poking on `if2` while VoHive owns
`if3`, or vice-versa). Only one owner per interface.

## What changed for darwin

- `internal/sockbind/` — `SO_BINDTODEVICE` (Linux) vs `IP_BOUND_IF` (darwin) for
  per-interface outbound binding; the `!linux && !darwin` stub errors explicitly.
- `internal/device/atport_override.go` — env-var AT-port injection that bypasses the
  `/sys` + `ttyUSB` discovery scan.
- `internal/modem/portrelease_{linux,other}.go` — the `fuser`-based force-release of a
  stale port holder is **Linux-only**; on macOS the "holder" is the PTY bridge and must
  never be killed.
- `internal/device/udev_other.go`, `internal/qmi/control_device_holders_other.go` —
  no-op stubs where Linux uses netlink `KOBJECT_UEVENT` / `/proc`.

## Known limitations

- SMS/voice require network registration in the CS or IMS domain. On VoLTE-only
  carriers (e.g. China Telecom) the CS domain returns `+CREG: 3` (denied) while the
  data domains register fine; SMS then needs IMS/VoLTE to be up. This is a
  carrier/SIM matter, identical on Linux.
- Traffic proxy "bind egress to a device NIC" and other netlink-driven features are
  Linux-only and degrade on darwin.
