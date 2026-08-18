//go:build !linux

package modem

// 非 Linux 平台不做 fuser 强制释放：端口可能是用户态 PTY 桥（macOS），
// 杀掉持有者会连桥一起打死，反而打不开串口。
const forceReleaseSupported = false
