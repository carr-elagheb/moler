# -*- coding: utf-8 -*-
"""
External-IO connections based on asyncio.

The only 3 requirements for these connections are:
(1) store Moler's connection inside self.moler_connection attribute
(2) plugin into Moler's connection the way IO outputs data to external world:

    self.moler_connection.how2send = self.send

(3) forward IO received data into self.moler_connection.data_received(data)
"""

__author__ = 'Grzegorz Latuszek'
__copyright__ = 'Copyright (C) 2018, Nokia'
__email__ = 'grzegorz.latuszek@nokia.com'

import atexit
import asyncio
import threading
import concurrent.futures

from moler.io.io_connection import IOConnection
from moler.io.io_exceptions import ConnectionTimeout
from moler.io.io_exceptions import RemoteEndpointDisconnected
from moler.io.io_exceptions import RemoteEndpointNotConnected
from moler.asyncio_runner import AsyncioEventThreadsafe
from moler.io.raw import TillDoneThread
from moler.exceptions import MolerException


class AsyncioTcp(IOConnection):
    """Implementation of TCP connection using asyncio."""
    def __init__(self, moler_connection, port, host="localhost", receive_buffer_size=64 * 4096, logger=None):
        """Initialization of TCP connection."""
        super(AsyncioTcp, self).__init__(moler_connection=moler_connection)
        self.moler_connection.how2send = self._send  # need to map synchronous methods
        # TODO: do we want connection.name?
        self.host = host
        self.port = port
        self.receive_buffer_size = receive_buffer_size
        self.logger = logger  # TODO: build default logger if given is None?
        self._stream_reader = None
        self._stream_writer = None
        self.connection_lost = None

    async def forward_connection_read_data(self):
        while True:
            data = await self._stream_reader.read(self.receive_buffer_size)  # if size not provided it reads till EOF (may block)
            if not data:
                break
            self._debug('< {}'.format(data))
            # forward data to moler-connection
            self.data_received(data)
        self.connection_lost.set_result(True)  # makes Future done

    async def open(self):
        """Open TCP connection."""
        self._debug('connecting to {}'.format(self))
        # If a task is canceled while it is waiting for another concurrent operation,
        # the task is notified of its cancellation by having a CancelledError exception
        # raised at the point where it is waiting
        try:
            self._stream_reader, self._stream_writer = await asyncio.open_connection(host=self.host, port=self.port)
            # self._stream_reader, self._stream_writer = await asyncio.wait_for(asyncio.open_connection(host=self.host, port=self.port), timeout=10)
        except asyncio.CancelledError as err:
            self._debug("CancelledError while awaiting for open_connection({}), err: {}".format(self, err))
            # TODO: stop child task of asyncio.open_connection
            raise
        else:
            self.connection_lost = asyncio.Future()  # delayed to be created in same loop as open()
            asyncio.ensure_future(self.forward_connection_read_data())
        self._debug('connection {} is open'.format(self))

    async def close(self):
        """Close TCP connection."""
        self._debug('closing {}'.format(self))
        self._stream_writer.close()
        if self.connection_lost:
            await self.connection_lost
        self._debug('connection {} is closed'.format(self))

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False  # reraise exceptions if any

    def _send(self, data):
        self._debug('> {}'.format(data))
        self._stream_writer.write(data)  # TODO: check if we have writer (if open)

    async def send(self, data):
        """
        Send data via TCP service.

        :param data: data
        :type data: str
        """
        self._send(data)
        await self._stream_writer.drain()

    def __str__(self):
        address = 'tcp://{}:{}'.format(self.host, self.port)
        return address

    def _debug(self, msg):  # TODO: refactor to class decorator or so
        if self.logger:
            self.logger.debug(msg)


class AsyncioInThreadTcp(IOConnection):
    """Implementation of TCP connection using asyncio running in dedicated thread."""
    def __init__(self, moler_connection, port, host="localhost", receive_buffer_size=64 * 4096, logger=None):
        """Initialization of TCP connection."""
        super(AsyncioInThreadTcp, self).__init__(moler_connection=moler_connection)
        # self.moler_connection.how2send = self._send  # need to map synchronous methods
        # TODO: do we want connection.name?
        self.host = host
        self.port = port
        self.receive_buffer_size = receive_buffer_size
        self.logger = logger  # TODO: build default logger if given is None?
        self._loop_thread = None
        self._loop = None
        self._loop_done = None
        self._async_tcp = AsyncioTcp(moler_connection=moler_connection, port=port, host=host,
                                     receive_buffer_size=receive_buffer_size, logger=logger)

    def _start_loop_thread(self):
        atexit.register(self.shutdown)
        self._loop = asyncio.new_event_loop()
        # self.logger.debug("created loop 4 thread: {}:{}".format(id(self._loop), self._loop))
        self._loop_done = AsyncioEventThreadsafe(loop=self._loop)
        self._loop.set_debug(enabled=True)
        self._loop_done.clear()
        loop_started = threading.Event()
        self._loop_thread = TillDoneThread(target=self._start_loop,
                                           done_event=self._loop_done,
                                           kwargs={'loop': self._loop,
                                                   'loop_started': loop_started,
                                                   'loop_done': self._loop_done})
        # self.logger.debug("created thread {} with loop {}:{}".format(self._loop_thread, id(self._loop), self._loop))
        self._loop_thread.start()
        # # await loop thread to be really started
        start_timeout = 0.5
        if not loop_started.wait(timeout=start_timeout):
            err_msg = "Failed to start asyncio loop thread within {} sec".format(start_timeout)
            self._loop_done.set()
            raise MolerException(err_msg)
        # self.logger.info("started new asyncio-in-thrd loop ...")

    def _start_loop(self, loop, loop_started, loop_done):
        # self.logger.info("starting new asyncio-in-thrd loop ...")
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._await_stop_loop(loop_started=loop_started, stop_event=loop_done))
        # self.logger.info("... asyncio-in-thrd loop done")

    async def _await_stop_loop(self, loop_started, stop_event):
        # stop_event may be set directly via self._loop_done.set()
        # or indirectly by TillDoneThread when python calls join on all active threads during python shutdown
        # self.logger.info("will await stop_event ...")
        loop_started.set()
        await stop_event.wait()
        # self.logger.info("... await stop_event done")

    def shutdown(self):
        # self.logger.debug("shutting down")
        if self._loop_done:
            self._loop_done.set()  # will exit from loop and holding it thread

    def _run_in_dedicated_thread(self, coroutine_to_run, timeout):
        # we are scheduling to other thread (so, can't use asyncio.ensure_future() )
        coro_future = asyncio.run_coroutine_threadsafe(coroutine_to_run, loop=self._loop)
        # run_coroutine_threadsafe returns future as concurrent.futures.Future() and not asyncio.Future
        # so, we can await it with timeout inside current thread
        try:
            return coro_future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as err:
            raise  # TODO: convert to Moler's timeout
        except concurrent.futures.CancelledError as err:
            raise

    def open(self):
        """Open TCP connection."""
        ret = super(AsyncioInThreadTcp, self).open()
        if self._loop_thread is None:
            try:
                self._start_loop_thread()
            except Exception as err_msg:
                # self.logger.error(err_msg)
                raise
        self._run_in_dedicated_thread(self._async_tcp.open(), timeout=0.5)
        return ret

    def close(self):
        """Close TCP connection."""
        # self._debug('closing {}'.format(self))
        ret = self._run_in_dedicated_thread(self._async_tcp.close(), timeout=0.5)
        self.shutdown()
        # await till finish of thread
        if self._loop_thread:
            self._loop_thread.join(timeout=1.0)
        # self._debug('connection {} is closed'.format(self))