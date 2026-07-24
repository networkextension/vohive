#!/usr/bin/env python3
"""把大疆/EG25 模组的 USB AT 接口(if2)桥接成一个 PTY，供 VoHive 当普通串口打开。

macOS 不给 class-0xFF 的 AT 接口加载 tty 驱动，所以没有 /dev/tty* 可用。
本脚本用 libusb 直接 claim if2 的 bulk 端点，再开一个 PTY：
  - master 端留在本进程，两条 pump 线程在 master ↔ USB 之间搬字节；
  - slave 端(/dev/ttysNNN)通过一个稳定 symlink 暴露出去，VoHive 打开它即可。

用法:
  python eg25_pty_bridge.py                 # 前台运行，Ctrl-C 退出
  python eg25_pty_bridge.py --link PATH     # 自定义 symlink 路径
  python eg25_pty_bridge.py --iface 3       # 桥接 if3 而非 if2

默认 symlink: <脚本所在目录>/eg25-at.pty
"""
import argparse
import os
import pty
import select
import signal
import sys
import threading
import tty

import usb.core
import usb.util

DJI = (0x2CA3, 0x4006)
QUECTEL = (0x2C7C, 0x0125)
DEFAULT_LINK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eg25-at.pty")


def find_dev():
    for vid, pid in (QUECTEL, DJI):
        dev = usb.core.find(idVendor=vid, idProduct=pid)
        if dev is not None:
            return dev, vid, pid
    sys.exit("未找到 2c7c:0125 或 2ca3:4006 设备")


def bulk_eps(intf):
    ep_out = ep_in = None
    for ep in intf:
        if usb.util.endpoint_type(ep.bmAttributes) != usb.util.ENDPOINT_TYPE_BULK:
            continue
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep
        else:
            ep_in = ep
    return ep_out, ep_in


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", type=int, default=2, help="桥接的 USB 接口号 (默认 2)")
    ap.add_argument("--link", default=DEFAULT_LINK, help="稳定 symlink 路径")
    args = ap.parse_args()

    dev, vid, pid = find_dev()
    print(f"设备: {vid:04x}:{pid:04x}")
    cfg = dev.get_active_configuration()
    try:
        intf = next(i for i in cfg if i.bInterfaceNumber == args.iface)
    except StopIteration:
        sys.exit(f"接口 if{args.iface} 不存在")
    ep_out, ep_in = bulk_eps(intf)
    if ep_out is None or ep_in is None:
        sys.exit(f"if{args.iface} 没有成对的 bulk 端点，不能当 AT 口")

    try:
        usb.util.claim_interface(dev, args.iface)
    except usb.core.USBError as e:
        sys.exit(f"claim if{args.iface} 失败(可能已被占用): {e}")

    master_fd, slave_fd = pty.openpty()
    tty.setraw(master_fd)
    tty.setraw(slave_fd)
    slave_name = os.ttyname(slave_fd)
    # 关键：本进程一直持有 slave_fd（但绝不读它），保证 PTY 始终「有 slave」，
    # 这样即使 VoHive 尚未打开 slave，模组的 URC(如 +CMTI)写进 master 也不会
    # 因「无 slave」触发 EIO 把搬运线程打死。VoHive 用路径再打开一次 slave 即可，
    # 多个 slave fd 并存；本进程不读，所有字节都归 VoHive。

    # 稳定 symlink，保证 VoHive 配置里的路径跨重启不变。
    try:
        if os.path.islink(args.link) or os.path.exists(args.link):
            os.unlink(args.link)
    except OSError:
        pass
    os.symlink(slave_name, args.link)
    print(f"PTY: {slave_name}")
    print(f"symlink: {args.link} -> {slave_name}")
    print(f"桥接 if{args.iface}  (OUT {ep_out.bEndpointAddress:#04x} / IN {ep_in.bEndpointAddress:#04x})")
    print("就绪。把 VOHIVE_AT_PORT_<id> 指到上面的 symlink。Ctrl-C 退出。")

    stop = threading.Event()

    def usb_to_pty():
        # 模组 → PTY：把 URC / AT 响应读出来写进 master
        while not stop.is_set():
            try:
                data = ep_in.read(ep_in.wMaxPacketSize, timeout=500)
            except usb.core.USBTimeoutError:
                continue
            except usb.core.USBError:
                if stop.is_set():
                    break
                continue
            if data:
                try:
                    os.write(master_fd, bytes(data))
                except OSError:
                    # 无 slave 打开的瞬间可能 EIO；本进程常驻持有 slave，
                    # 正常不会走到这里。保守起见丢弃本片继续，不打死线程。
                    continue

    def pty_to_usb():
        # PTY → 模组：VoHive 写来的 AT 命令搬给 bulk OUT
        while not stop.is_set():
            r, _, _ = select.select([master_fd], [], [], 0.5)
            if not r:
                continue
            try:
                data = os.read(master_fd, 4096)
            except OSError:
                break
            if not data:
                continue
            try:
                ep_out.write(data, timeout=2000)
            except usb.core.USBError:
                if stop.is_set():
                    break

    t1 = threading.Thread(target=usb_to_pty, daemon=True)
    t2 = threading.Thread(target=pty_to_usb, daemon=True)
    t1.start()
    t2.start()

    def shutdown(*_):
        stop.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while not stop.is_set():
            stop.wait(0.5)
    finally:
        stop.set()
        for fd in (master_fd, slave_fd):
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            usb.util.release_interface(dev, args.iface)
        except usb.core.USBError:
            pass
        try:
            if os.path.islink(args.link):
                os.unlink(args.link)
        except OSError:
            pass
        print("\n已退出，接口已释放。")


if __name__ == "__main__":
    main()
