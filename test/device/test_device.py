# -*- coding: utf-8 -*-

__author__ = 'Grzegorz Latuszek, Michal Ernst, Marcin Usielski'
__copyright__ = 'Copyright (C) 2018-2019, Nokia'
__email__ = 'grzegorz.latuszek@nokia.com, michal.ernst@nokia.com, marcin.usielski@nokia.com'

import pytest


def test_device_directly_created_must_be_given_io_connection(buffer_connection):
    from moler.device.unixlocal import UnixLocal

    dev = UnixLocal(io_connection=buffer_connection)
    assert dev.io_connection == buffer_connection


def test_device_add_neighbour_device(buffer_connection):
    from moler.device.unixlocal import UnixLocal

    dev1 = UnixLocal(io_connection=buffer_connection)
    dev2 = UnixLocal(io_connection=buffer_connection)
    neighbour_devices = dev1.get_neighbour_devices(device_type=UnixLocal)
    assert 0 == len(neighbour_devices)

    dev1.add_neighbour_device(neighbour_device=dev2, bidirectional=True)
    neighbour_devices = dev1.get_neighbour_devices(device_type=UnixLocal)
    assert 1 == len(neighbour_devices)

    neighbour_devices = dev2.get_neighbour_devices(device_type=UnixLocal)
    assert 1 == len(neighbour_devices)

    # device is added only once
    dev1.add_neighbour_device(neighbour_device=dev2)
    neighbour_devices = dev1.get_neighbour_devices(device_type=UnixLocal)
    assert 1 == len(neighbour_devices)

    neighbour_devices = dev1.get_neighbour_devices(device_type=None)
    assert 1 == len(neighbour_devices)

    neighbour_devices = dev1.get_neighbour_devices(device_type=int)
    assert 0 == len(neighbour_devices)


def test_device_add_neighbour_device_without_bidirectional(buffer_connection):
    from moler.device.unixlocal import UnixLocal
    dev1 = UnixLocal(io_connection=buffer_connection)
    dev2 = UnixLocal(io_connection=buffer_connection)

    dev1.add_neighbour_device(neighbour_device=dev2, bidirectional=False)

    neighbour_devices = dev1.get_neighbour_devices(device_type=UnixLocal)
    assert 1 == len(neighbour_devices)

    neighbour_devices = dev2.get_neighbour_devices(device_type=UnixLocal)
    assert 0 == len(neighbour_devices)


def test_device_may_be_created_on_named_connection(configure_net_1_connection):
    from moler.device.unixlocal import UnixLocal

    dev = UnixLocal.from_named_connection(connection_name='net_1')
    assert dev.io_connection is not None
    assert dev.io_connection.name == 'net_1'


def test_device_unix_can_return_cd_command(configure_net_1_connection):
    from moler.device.unixlocal import UnixLocal
    from moler.cmd.unix.cd import Cd

    ux = UnixLocal.from_named_connection(connection_name='net_1')
    ux.establish_connection()
    assert hasattr(ux, 'get_cmd')
    assert isinstance(
        ux.get_cmd(
            cmd_name='cd',
            cmd_params={
                "path": "/home/user/"
            }
        ),
        Cd
    )


# --------------------------- resources ---------------------------


@pytest.yield_fixture
def configure_net_1_connection():
    from moler.config import connections as conn_cfg

    conn_cfg.set_default_variant(io_type='memory', variant="threaded")
    conn_cfg.define_connection(name='net_1', io_type='memory')
    yield
    conn_cfg.clear()
