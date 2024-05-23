# SPDX-License-Identifier: GPL-2.0
# (C) Copyright 2023, Advanced Micro Devices, Inc.

import pytest
import u_boot_utils
import test_net

"""
Note: This test relies on boardenv_* containing configuration values to define
which the network environment available for testing. Without this, this test
will be automatically skipped.

For example:

# Details regarding a boot image file that may be read from a TFTP server. This
# variable may be omitted or set to None if TFTP boot testing is not possible
# or desired.
env__net_tftp_bootable_file = {
    'fn': 'image.ub',
    'addr': 0x10000000,
    'size': 5058624,
    'crc32': 'c2244b26',
    'pattern': 'Linux',
    'config': 'config@2',
    'timeout': 50000,
}

# Here is the example of FIT image configurations:
configurations {
    default = "config@1";
    config@1 {
        description = "Boot Linux kernel with config@1";
        kernel = "kernel@0";
        fdt = "fdt@0";
        ramdisk = "ramdisk@0";
        hash@1 {
            algo = "sha1";
        };
    };
    config@2 {
        description = "Boot Linux kernel with config@2";
        kernel = "kernel@1";
        fdt = "fdt@1";
        ramdisk = "ramdisk@1";
        hash@1 {
            algo = "sha1";
        };
    };
};

# Details regarding a file that may be read from a TFTP server. This variable
# may be omitted or set to None if PXE testing is not possible or desired.
env__net_pxe_bootable_file = {
    'fn': 'default',
    'addr': 0x10000000,
    'size': 74,
    'timeout': 50000,
    'pattern': 'Linux',
    'valid_label': '1',
    'invalid_label': '2',
    'exp_str_invalid': 'Skipping install for failure retrieving',
    'local_label': '3',
    'exp_str_local': 'missing environment variable: localcmd',
    'empty_label': '4',
    'exp_str_empty': 'No kernel given, skipping boot',
}

# Here is the example of pxe configuration file ordered based on the execution
# flow:
1) /tftpboot/pxelinux.cfg/default-arm-zynqmp

    menu include pxelinux.cfg/default-arm
    timeout 50

    default Linux

2) /tftpboot/pxelinux.cfg/default-arm

    menu title Linux boot selections
    menu include pxelinux.cfg/default

    label install
        menu label Invalid boot
        kernel kernels/install.bin
        append console=ttyAMA0,38400 debug earlyprintk
        initrd initrds/uzInitrdDebInstall

    label local
        menu label Local boot
        append root=/dev/sdb1
        localboot 1

    label boot
        menu label Empty boot

3) /tftpboot/pxelinux.cfg/default

    label Linux
        menu label Boot kernel
        kernel Image
        fdt system.dtb
        initrd rootfs.cpio.gz.u-boot
"""

def setup_tftpboot_boot(u_boot_console):
    f = u_boot_console.config.env.get('env__net_tftp_bootable_file', None)
    if not f:
        pytest.skip('No TFTP bootable file to read')

    test_net.test_net_dhcp(u_boot_console)
    test_net.test_net_setup_static(u_boot_console)

    addr = f.get('addr', None)
    if not addr:
        addr = u_boot_utils.find_ram_base(u_boot_console)

    fn = f['fn']
    output = u_boot_console.run_command('tftpboot %x %s' % (addr, fn))
    expected_text = 'Bytes transferred = '
    sz = f.get('size', None)
    if sz:
        expected_text += '%d' % sz
    assert expected_text in output

    expected_crc = f.get('crc32', None)
    output = u_boot_console.run_command('crc32 %x $filesize' % addr)
    if expected_crc:
        assert expected_crc in output

    pattern = f.get('pattern')
    config = f.get('config', None)
    timeout = f.get('timeout', 50000)

    return addr, pattern, timeout, config

@pytest.mark.buildconfigspec('cmd_net')
def test_net_tftpboot_boot(u_boot_console):
    """Boot the loaded image

    A boot file (fit image) is downloaded from the TFTP server and booted using
    bootm command with the default fit configuration, its boot log pattern are
    validated.

    The details of the file to download are provided by the boardenv_* file;
    see the comment at the beginning of this file.
    """
    addr, pattern, timeout, imcfg = setup_tftpboot_boot(u_boot_console)
    with u_boot_console.temporary_timeout(timeout):
        try:
            # wait_for_prompt=False makes the core code not wait for the U-Boot
            # prompt code to be seen, since it won't be on a successful kernel
            # boot
            u_boot_console.run_command('bootm %x'% addr, wait_for_prompt=False)
            # You might want to expand wait_for() with options to add extra bad
            # patterns which immediately indicate a failed boot, or add a new
            # "with object" function u_boot_console.enable_check() that can
            # cause extra patterns like the U-Boot console prompt, U-Boot boot
            # error messages, kernel boot error messages, etc. to fail the
            # wait_for().

            # Wait for boot log pattern
            u_boot_console.wait_for(pattern)
        finally:
            # This forces the console object to be shutdown, so any subsequent
            # test will reset the board back into U-Boot. We want to force this
            # no matter whether the kernel boot passed or failed.
            u_boot_console.drain_console()
            u_boot_console.cleanup_spawn()

@pytest.mark.buildconfigspec('cmd_net')
def test_net_tftpboot_boot_config(u_boot_console):
    """Boot the loaded image from FIT image configuration

    A boot file (fit image) is downloaded from the TFTP server and booted using
    bootm command with the custom fit configuration, its boot log pattern are
    validated.

    The details of the file to download are provided by the boardenv_* file;
    see the comment at the beginning of this file.
    """
    addr, pattern, timeout, imcfg = setup_tftpboot_boot(u_boot_console)
    response = u_boot_console.run_command('imi %x' % addr)
    if not imcfg or not imcfg in response:
        pytest.skip('The custom configuration not found')

    with u_boot_console.temporary_timeout(timeout):
        try:
            u_boot_console.run_command(
                'bootm %x#%s' % (addr, imcfg), wait_for_prompt=False
            )
            u_boot_console.wait_for(pattern)
        finally:
            u_boot_console.drain_console()
            u_boot_console.cleanup_spawn()

def setup_pxe_boot(u_boot_console):
    f = u_boot_console.config.env.get('env__net_pxe_bootable_file', None)
    if not f:
        pytest.skip('No PXE bootable file to read')

    test_net.test_net_dhcp(u_boot_console)
    test_net.test_net_setup_static(u_boot_console)
    return f

@pytest.mark.buildconfigspec('cmd_net')
@pytest.mark.buildconfigspec('cmd_pxe')
def test_net_pxe_boot(u_boot_console):
    """Test the pxe boot command.

    A pxe configuration file is downloaded from the TFTP server and interpreted
    to boot the images mentioned in pxe configuration file.

    The details of the file to download are provided by the boardenv_* file;
    see the comment at the beginning of this file.
    """

    f = setup_pxe_boot(u_boot_console)
    addr = f.get('addr', None)
    timeout = f.get('timeout', u_boot_console.p.timeout)
    fn = f['fn']

    with u_boot_console.temporary_timeout(timeout):
        output = u_boot_console.run_command('pxe get')

    expected_text = 'Bytes transferred = '
    sz = f.get('size', None)
    if sz:
        expected_text += '%d' % sz
    assert 'TIMEOUT' not in output
    assert expected_text in output
    assert "Config file 'default.boot' found" in output

    pattern = f.get('pattern')
    if not addr:
        pxe_boot_cmd = 'pxe boot'
    else:
        pxe_boot_cmd = 'pxe boot %x' % addr

    with u_boot_console.temporary_timeout(timeout):
        try:
            u_boot_console.run_command(pxe_boot_cmd, wait_for_prompt=False)
            u_boot_console.wait_for(pattern)
        finally:
            u_boot_console.drain_console()
            u_boot_console.cleanup_spawn()

@pytest.mark.buildconfigspec('cmd_net')
@pytest.mark.buildconfigspec('cmd_pxe')
def test_net_pxe_boot_config(u_boot_console):
    """Test the pxe boot command by selecting different combination of labels

    A pxe configuration file is downloaded from the TFTP server and interpreted
    to boot the images mentioned in pxe configuration file.

    The details of the file to download are provided by the boardenv_* file;
    see the comment at the beginning of this file.
    """

    f = setup_pxe_boot(u_boot_console)
    addr = f.get('addr', None)
    timeout = f.get('timeout', u_boot_console.p.timeout)
    fn = f['fn']
    local_label = f['local_label']
    empty_label = f['empty_label']
    exp_str_local = f['exp_str_local']
    exp_str_empty = f['exp_str_empty']

    with u_boot_console.temporary_timeout(timeout):
        output = u_boot_console.run_command('pxe get')

    expected_text = 'Bytes transferred = '
    sz = f.get('size', None)
    if sz:
        expected_text += '%d' % sz
    assert 'TIMEOUT' not in output
    assert expected_text in output
    assert "Config file 'default.boot' found" in output

    pattern = f.get('pattern')
    if not addr:
        pxe_boot_cmd = 'pxe boot'
    else:
        pxe_boot_cmd = 'pxe boot %x' % addr

    with u_boot_console.temporary_timeout(timeout):
        try:
            u_boot_console.run_command(pxe_boot_cmd, wait_for_prompt=False)

            # pxe config is loaded where multiple labels are there and need to
            # select particular label to boot and check for expected string
            # In this case, local label is selected and it should look for
            # localcmd env variable and if that variable is not defined it
            # should not boot it and come out to u-boot prompt
            u_boot_console.wait_for('Enter choice:')
            u_boot_console.run_command(local_label, wait_for_prompt=False)
            expected_str = u_boot_console.p.expect([exp_str_local])
            assert (
                expected_str == 0
            ), f'Expected string: {exp_str_local} did not match!'

            # In this case, empty label is selected and it should look for
            # kernel image path and if it is not set it should fail it and load
            # default label to boot
            u_boot_console.run_command(pxe_boot_cmd, wait_for_prompt=False)
            u_boot_console.wait_for('Enter choice:')
            u_boot_console.run_command(empty_label, wait_for_prompt=False)
            expected_str = u_boot_console.p.expect([exp_str_empty])
            assert (
                expected_str == 0
            ), f'Expected string: {exp_str_empty} did not match!'

            u_boot_console.wait_for(pattern)
        finally:
            u_boot_console.drain_console()
            u_boot_console.cleanup_spawn()

@pytest.mark.buildconfigspec('cmd_net')
@pytest.mark.buildconfigspec('cmd_pxe')
def test_net_pxe_boot_config_invalid(u_boot_console):
    """Test the pxe boot command by selecting invalid label

    A pxe configuration file is downloaded from the TFTP server and interpreted
    to boot the images mentioned in pxe configuration file.

    The details of the file to download are provided by the boardenv_* file;
    see the comment at the beginning of this file.
    """

    f = setup_pxe_boot(u_boot_console)
    addr = f.get('addr', None)
    timeout = f.get('timeout', u_boot_console.p.timeout)
    fn = f['fn']
    invalid_label = f['invalid_label']
    exp_str_invalid = f['exp_str_invalid']

    with u_boot_console.temporary_timeout(timeout):
        output = u_boot_console.run_command('pxe get')

    expected_text = 'Bytes transferred = '
    sz = f.get('size', None)
    if sz:
        expected_text += '%d' % sz
    assert 'TIMEOUT' not in output
    assert expected_text in output
    assert "Config file 'default.boot' found" in output

    pattern = f.get('pattern')
    if not addr:
        pxe_boot_cmd = 'pxe boot'
    else:
        pxe_boot_cmd = 'pxe boot %x' % addr

    with u_boot_console.temporary_timeout(timeout):
        try:
            u_boot_console.run_command(pxe_boot_cmd, wait_for_prompt=False)

            # pxe config is loaded where multiple labels are there and need to
            # select particular label to boot and check for expected string
            # In this case invalid label is selected, it should load invalid
            # label and if it fails it should load the default label to boot
            u_boot_console.wait_for('Enter choice:')
            u_boot_console.run_command(invalid_label, wait_for_prompt=False)
            expected_str = u_boot_console.p.expect([exp_str_invalid])
            assert (
                expected_str == 0
            ), f'Expected string: {exp_str_invalid} did not match!'

            u_boot_console.wait_for(pattern)
        finally:
            u_boot_console.drain_console()
            u_boot_console.cleanup_spawn()
