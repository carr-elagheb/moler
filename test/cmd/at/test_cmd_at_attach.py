# -*- coding: utf-8 -*-
"""
Testing AtCmdAttach commands.
"""

__author__ = 'Grzegorz Latuszek'
__copyright__ = 'Copyright (C) 2020, Nokia'
__email__ = 'grzegorz.latuszek@nokia.com'

import pytest


# --------------------------- testing base class ---------------------------
def test_calling_at_cmd_attach_returns_expected_result(buffer_connection):
    from moler.cmd.at import attach
    at_cmd_attach = attach.AtCmdAttach(connection=buffer_connection.moler_connection,
                                       **attach.COMMAND_KWARGS_ver_execute)
    buffer_connection.remote_inject_response([attach.COMMAND_OUTPUT_ver_execute])
    result = at_cmd_attach()
    assert result == attach.COMMAND_RESULT_ver_execute


def test_at_cmd_attach_has_default_timeout_180sec(buffer_connection):
    from moler.cmd.at import attach
    at_cmd_attach = attach.AtCmdAttach(connection=buffer_connection.moler_connection,
                                       **attach.COMMAND_KWARGS_ver_execute)
    assert at_cmd_attach.timeout == 180


def test_calling_at_cmd_attach_timeouts_after_1sec(buffer_connection):
    from moler.cmd.at import attach
    from moler.exceptions import CommandTimeout
    import time
    at_cmd_attach = attach.AtCmdAttach(connection=buffer_connection.moler_connection,
                                       **attach.COMMAND_KWARGS_ver_execute)
    at_cmd_attach.timeout = 1
    buffer_connection.remote_inject_response(["AT+CGATT=1\n"])
    start_time = time.time()
    with pytest.raises(CommandTimeout) as error:
        at_cmd_attach()
    duration = time.time() - start_time
    assert duration > 1.0
    assert duration < 1.2


def test_calling_at_cmd_attach_timeouts_on_no_output(buffer_connection):
    from moler.cmd.at import attach
    from moler.exceptions import CommandTimeout
    import time
    at_cmd_attach = attach.AtCmdAttach(connection=buffer_connection.moler_connection,
                                       **attach.COMMAND_KWARGS_ver_execute)
    at_cmd_attach.timeout = 1
    start_time = time.time()
    with pytest.raises(CommandTimeout) as error:
        at_cmd_attach()
    duration = time.time() - start_time
    assert duration > 1.0
    assert duration < 1.2
    assert at_cmd_attach.command_output == ''


def test_calling_at_cmd_attach_fails_on_erroneous_output(buffer_connection):
    from moler.cmd.at import attach
    from moler.cmd.at.at import AtCommandFailure

    at_cmd_attach = attach.AtCmdAttach(connection=buffer_connection.moler_connection,
                                       **attach.COMMAND_KWARGS_ver_execute)
    at_cmd_attach.timeout = 1
    buffer_connection.remote_inject_response(["AT+CGATT=1\nERROR"])

    with pytest.raises(AtCommandFailure) as error:
        at_cmd_attach()
