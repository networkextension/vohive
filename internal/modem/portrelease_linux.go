//go:build linux

package modem

// forceReleaseSupported 仅在 Linux 打开：用 fuser 杀掉抢占 ttyUSB 的陈旧
// ModemManager/进程是 Linux 串口语义。其它平台（如 macOS 走 PTY 桥接）绝不能
// 杀端口持有者——那正是我们的桥接进程。
const forceReleaseSupported = true
