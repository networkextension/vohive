//go:build darwin

package sockbind

import (
	"net"

	"golang.org/x/sys/unix"
)

// BindToDevice 把 socket 出站绑定到指定网卡。
// darwin 没有 SO_BINDTODEVICE，等价物是按接口索引的 IP_BOUND_IF / IPV6_BOUND_IF；
// 具体 socket 只属于一个地址族，两个 setsockopt 有一个成功即视为绑定成功。
func BindToDevice(fd uintptr, iface string) error {
	ifi, err := net.InterfaceByName(iface)
	if err != nil {
		return err
	}
	err4 := unix.SetsockoptInt(int(fd), unix.IPPROTO_IP, unix.IP_BOUND_IF, ifi.Index)
	err6 := unix.SetsockoptInt(int(fd), unix.IPPROTO_IPV6, unix.IPV6_BOUND_IF, ifi.Index)
	if err4 != nil && err6 != nil {
		return err4
	}
	return nil
}
