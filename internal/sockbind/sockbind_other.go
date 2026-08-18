//go:build !linux && !darwin

package sockbind

import "errors"

func BindToDevice(fd uintptr, iface string) error {
	return errors.New("sockbind: bind-to-device not supported on this platform")
}
