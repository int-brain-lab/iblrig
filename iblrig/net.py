"""
Network communication between rigs.

An example of a remote_rigs.yaml file:

```yaml
neuropixel: '12.134.270.1'
'cameras:left': 'tcp://0.123.456.7:9998'
'cameras:right': 'tcp://0.123.456.6:9998'
tasks: 'udp://123.654.8.8'
```

TODO case study: starts services but times out due to one service.
 How to restart without stopping services? Perhaps it can throw a
 warning if the status is running but continue on anyway?
TODO perhaps confirmed_send should ensure that data is list with
 element 1 being an exp message
TODO handle message timeouts in thread
TODO Version service protocol
TODO Send version info with exp info
TODO Signal thread stop in mixin run method
TODO Rewrite video session function with loop
TODO Test for file lock context manager
TODO Implement video end and cleanups
TODO tests for clear_callbacks cancel future
TODO test error_received and connection_lost
TODO Services init alyx callback
TODO await all timeout tests
TODO test individual CammeraSession methods
TODO Test for keyboard input
TODO Process keyboard input
TODO Document read stdin
TODO Use queue for async run loop
TODO Finish prep ephys session

Examples
--------
Send a standard message (e.g. start) to all rigs and await their responses:

>>> responses = await services.start(exp_ref)

Send a standard message to all rigs without awaiting responses:

>>> for service in services.values():
...     await service.init()

Send exp info message to all rigs and await their responses:

>>> responses = await self.services._signal(ExpMessage.EXPINFO, 'confirmed_send', [ExpMessage.EXPINFO, ...])

Send exp info message to all rigs without awaiting responses:

>>> for service in services.values():
...     await service.confirmed_send([ExpMessage.EXPINFO, ...])

Request status from a single service (await echo):

>>> await services['cameras'].confirmed_send([ExpMessage.EXPSTATUS])

Send message to a single service without awaiting echo:
NB: use with causion: can cause infinite loops if both not correctly configured

>>> services['cameras'].send([ExpMessage.EXPSTATUS])

"""

import asyncio
import logging
import sys
import threading
import time
from dataclasses import dataclass

# from threading import Thread
from urllib.parse import urlparse
from weakref import WeakValueDictionary

import yaml

import one.params
from iblrig.path_helper import get_local_and_remote_paths
from iblutil.io import net
from iblutil.io.params import FileLock
from one.api import OneAlyx
from one.webclient import AlyxClient

log = logging.getLogger(__name__)
log.setLevel(10)


class Singleton(type):
    """A singleton class."""

    _instances = WeakValueDictionary()  # instance automatically destroyed when no longer referenced

    def __call__(cls, *args, **kwargs):
        """Ensure the same instance is returned."""
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Auxiliaries(metaclass=Singleton):
    services = None
    """iblutil.io.net.app.Services: A map of remote services."""
    refresh_rate = 0.2
    """float: How long to wait between checking message queue."""
    _clients = {}
    """dict: Map of remote service names and their corresponding URI."""
    _queued: dict[float, list] = {}
    """dict: The messages queued for delivery by async thread."""
    _awaiting: dict[threading.Event]
    _log: dict[float, dict] = {}
    """dict: Map of request times and the remote responses."""
    stop_event = None
    """threading.Event: A thread event. Once set, thread stops listening and clean up services."""

    def __new__(cls, *args, **kwargs):
        # FIXME Singleton pattern most likely not necessary
        cls.response_received = threading.Condition()
        cls.connected = threading.Condition()
        cls.stop_event = threading.Event()
        return super().__new__(cls)

    def __init__(self, clients):
        """
        Connect to and communicate with one or more remote rigs synchronously.

        Parameters
        ----------
        clients : dict[str, str]
            A map of name to URI.
        """
        # Load clients
        self._clients = clients or {}
        self.thread = threading.Thread(target=asyncio.run, args=(self.listen(),), name='network_coms')
        self.thread.start()

    @property
    def is_connected(self) -> bool:
        """bool: True if successfully connected to services."""
        return any(self.services or []) and self.services.is_connected

    @property
    def is_running(self) -> bool:
        """bool: True if listen is running on another thread."""
        return self.stop_event and not self.stop_event.is_set()

    def clear_message_queue(self):
        """
        Clear queued messages.

        Returns
        -------
        int
            The number of aborted messages.
        """
        n_aborted = len(self._queued)
        self._queued.clear()
        log.debug('%i remote services messages aborted', n_aborted)
        return n_aborted

    async def cleanup(self, notify_services=False):
        """
        Close connections and cleanup services.

        This method closes all service communicators and cancels any pending callbacks.

        Parameters
        ----------
        notify_services : bool
            If true, send EXPCLEANUP message to remote devices before cleanup.
        """
        self._queued.clear()
        if notify_services:  # Send cleanup message to services without await response
            await self.services._signal(net.base.ExpMessage.EXPCLEANUP, 'cleanup', reverse=True, concurrent=True)
        self.services.close()

    def close(self):
        """Close communicators and wait for thread to terminate."""
        self.clear_message_queue()
        self.stop_event.set()
        self.thread.join(timeout=5)  # wait for thread to exit

    async def create(self):
        """
        Create remote services object.

        Instantiates communicator objects which establish the UDP connections, wraps them in the
        Service class for bulk messaging, sets connected property to True and assigns some logging
        callbacks. This should be called from a daemon thread.
        """
        with self.connected:
            remote_rigs = [await net.app.EchoProtocol.client(uri, name) for name, uri in self._clients.items()]
            self.services = net.app.Services(remote_rigs, timeout=10)
            self.connected.notify()
        log.debug('Connected...')
        # Assign a callback to all clients
        self.services.assign_callback('EXPSTART', lambda _, addr: print('{}:{} started'.format(*addr)))

    async def listen(self):
        """
        Listen for messages in queue and push to remote services.

        Creates service communicators then awaits messages added to the queue. Once added, these
        are sent to the remote services and the collated responses are added to the log.
        Exits only after stop event is set. This should be called from a daemon thread.
        """
        await self.create()
        while not self.stop_event.is_set():
            if any(queue := sorted(self._queued)):
                request_time = queue[0]
                t_str = time.strftime('%H:%M:%S', time.localtime(request_time))
                event, args, kwargs = self._queued[request_time]
                if not isinstance(event, net.base.ExpMessage):
                    raise TypeError('invalid message cued at ' + t_str)
                log.debug('Sending %s message requested at %s', event.name, t_str)
                try:
                    match event:
                        case net.base.ExpMessage.EXPSTART:
                            responses = await self.services.start(*args)
                        case net.base.ExpMessage.EXPINIT:
                            responses = await self.services.init(*args)
                        case net.base.ExpMessage.EXPEND | net.base.ExpMessage.EXPINTERRUPT:
                            responses = await self.services.stop(args, immediately=event is net.base.ExpMessage.EXPINTERRUPT)
                        case net.base.ExpMessage.EXPINFO:
                            # TODO Instead of waiting for all responses, cancel futures when main sync responds?
                            # async def first(aiterable, condition=lambda i: True):
                            #     for x in aiterable:
                            #         x = await x
                            #         if condition(x):
                            #             yield x
                            #
                            # res = await anext(first(asyncio.as_completed(tasks), lambda r: r[-1]['main_sync']))
                            responses = await self.services.info(event, *args)
                        case net.base.ExpMessage.ALYX:
                            responses = await self.services.alyx(*args)
                        case _:
                            responses = NotImplementedError(event)
                except asyncio.TimeoutError as ex:  # TODO broaden exception
                    log.error('Timeout error: %s', ex)
                    responses = ex
                with self.response_received:
                    self._log[request_time] = responses
                    if request_time in self._queued:  # may have been removed if `close` called
                        del self._queued[request_time]  # remove from queue
                    self.response_received.notify()
            if not self.stop_event.is_set():
                await asyncio.sleep(self.refresh_rate)
        await self.cleanup()

    def push(self, message: net.base.ExpMessage, *args, wait=False, **kwargs):
        """Queue message for dispatch to remote services.

        This method synchronously logs the request time and pushes the message to the queue for the
        asynchronous thread to handle.

        Parameters
        ----------
        message : iblutil.io.net.base.ExpMessage
            An experiment message to send to remote services.
        args : any
            One or more optional variables to send.
        wait : bool
            If True, this method is blocking and once all messages are received (or timed out) the
            collated responses are returned. Otherwise the request timestamp is returned for use as
            a log key when fetching the responses in a non-blocking manner.
        kwargs
            Optional keyword arguments to use in calling communicator methods (currently unused).

        Returns
        -------
        Exception | dict | float
            An exception if failed to receive all responses in time, otherwise a map of service
            name and response if wait is true, or the request time if wait is false.

        Raises
        ------
        RuntimeError
            The async thread failed to return a response, most likely due to an error in the listen
            method.
        """
        request_time = time.time()
        message = net.base.ExpMessage.validate(message, allow_bitwise=False)
        assert request_time not in self._queued, 'too many requests sent at once'
        assert self.is_running
        # The expected max time for the thread to return control
        thread_timeout = self.services.timeout + self.refresh_rate
        with self.response_received:  # lock thread so it can't process the message before we can wait on it (very unlikely)
            self._queued[request_time] = [message, args, kwargs]
            if not wait:
                return request_time
            success = self.response_received.wait_for(lambda: request_time in self._log, timeout=thread_timeout)
            if not success:
                # probably a timeout or other failure
                raise RuntimeError('Thread failed to return')
            return self._log[request_time]


def install_alyx_token(base_url, token):
    """Save Alyx token sent from remote device.

    Saves an Alyx token into the ONE params for a given database instance.

    Parameters
    ----------
    base_url : str
        The Alyx database URL.
    token : dict[str, dict]
        The token in the form {username: {'token': token}}.

    Returns
    -------
    bool
        True if the token was far a user not already cached.
    """
    par = one.params.get(base_url, silent=True).as_dict()
    is_new_user = next(iter(token), None) not in par.get('TOKEN', {})
    par.setdefault('TOKEN', {}).update(token)
    one.params.save(par, base_url)
    return is_new_user


def update_alyx_token(data, _, alyx=None, one=None):
    """Callback to update instance with Alyx token.

    Parameters
    ----------
    data : (str, dict)
        Tuple containing the Alyx database URL and token dict.
    addr : (str, int)
        The address of the remote host that sent the Alyx data (unused).
    alyx : one.webclient.AlyxClient
        An optional instance of Alyx to update with the token.
    one.api.OneAlyx
        An optional instance of ONE to update with the token.

    Returns
    -------
    bool
        If True, the provided alyx or one instance was successfully updated with the token.
    """
    base_url, token = data
    if not (base_url and token) or not (alyx or one):
        return False
    if one and not isinstance(one, OneAlyx):
        return False
    username = next(iter(token))
    if not alyx:
        alyx = one._web_client or AlyxClient(base_url=base_url, username=username, silent=True)
    # Update alyx object
    alyx._par = (
        alyx._par.set('ALYX_URL', base_url)
        .set('ALYX_LOGIN', username)
        .set('TOKEN', {**alyx._par.as_dict().get('TOKEN', {}), **token})
    )
    alyx._token = alyx._par.TOKEN[username]
    alyx._headers = {'Authorization': f'Token {list(alyx._token.values())[0]}', 'Accept': 'application/json'}
    alyx.user = username
    alyx.base_url = base_url
    alyx.silent = True  # ensure Alyx doesn't attempt to prompt user for input
    # Update ONE object
    if one:
        one._web_client = alyx
        one.mode = 'remote' if alyx.is_logged_in else 'local'
    return alyx.is_logged_in


@dataclass
class ExpInfo:
    """A standard experiment information structure."""

    main_sync: bool
    exp_ref: str
    experiment_description: dict
    master: bool


def get_remote_devices_file():
    """
    Return the location of the remote devices YAML file.

    Returns
    -------
    pathlib.Path, None
        The full path to the remote devices YAML file in the remote data folder, or None if the folder is not defined.
    """
    if remote_data_folder := get_local_and_remote_paths()['remote_data_folder']:
        return remote_data_folder.joinpath('remote_devices.yaml')


def get_remote_devices():
    """
    Return map of device name to network URI.

    Returns
    -------
    dict[str, str]
        A map of device name to network URI, e.g. {'cameras': 'udp://127.0.0.1:11001'}.

    TODO Move to pathhelper?
    """
    remote_devices = {}
    if (remote_devices_file := get_remote_devices_file()) and remote_devices_file.exists():
        with open(remote_devices_file) as f:
            remote_devices = yaml.safe_load(f)
    return remote_devices


async def get_server_communicator(service_uri, name: str):
    """

    Parameters
    ----------
    service_uri : bool, None, str
    name : str

    Returns
    -------
    iblutil.io.net.app.EchoProtocol, None
        A Communicator instance, or None if server_uri is False.
    bool
        True if the URI matches the one in the file, False otherwise.
    """
    if service_uri is False:
        return None, False
    if service_uri in (None, True, ''):
        lan_ip = net.base.hostname2ip()  # Local area network IP of this PC
        service_uri = net.base.validate_uri(lan_ip)  # Listen for server message on this local port
    return await check_uri_match(await net.app.EchoProtocol.server(service_uri, name=name))


async def check_uri_match(com: net.app.EchoProtocol, update=None) -> (net.app.EchoProtocol, bool):
    """
    Log warning if URI in remote devices is wrong.

    NB: Currently does not check if the protocol matches, and does not resolve hostnames.

    Parameters
    ----------
    com : iblutil.io.net.app.EchoProtocol
        A Communicator instance to compare to the devices file.
    update : bool, None
        If True, update the remote devices YAML file. If False, do not update the remote devices YAML file. If None,
        only updates if the file exists.

    Returns
    -------
    iblutil.io.net.app.EchoProtocol
        The same Communicator instance.
    bool
        True if the URI matches the one in the file, False otherwise.  When update is True, True should always be
        returned.

    Raises
    ------
    FileNotFoundError
        Raised when update is True but the remote devices YAML file does not exist on disk.
    """
    match = False
    remote_devices = get_remote_devices() or {}
    if expected := remote_devices.get(com.name):
        expected = net.base.validate_uri(expected)
        ip, _, port = urlparse(expected).netloc.rpartition(':')
        match = (ip, int(port)) == (com.hostname, com.port)
        if not match:
            log.warning(
                'remote devices specifies %s as %s:%s, communicator listening on %s:%s.', com.name, ip, port, com.hostname, port
            )

    if update is not False and not match:
        remote_devices_file = get_remote_devices_file()
        if update is True and not remote_devices_file.exists():
            raise FileNotFoundError('Remote data folder not defined.')
        if remote_devices_file:
            remote_devices_file.parent.mkdir(exist_ok=True, parents=True)
            async with FileLock(remote_devices_file, timeout=10, log=log):
                with remote_devices_file.open('w') as fp:
                    remote_devices.update({com.name: com.server_uri})
                    yaml.safe_dump(remote_devices, fp)
                match = True
    return com, match


async def read_stdin(loop=None):
    """
    Asynchronously reads lines from standard input.

    Allows asynchronous reading of user keyboard input. Currently there is no cross-platform way to listen to
    keypresses, but this function comes close.

    Parameters
    ----------
    loop : asyncio.AbstractEventLoop
        An optional event loop to use.

    Yields
    -------
    str
        A line of text from the standard input, if available.
    """
    loop = loop or asyncio.get_event_loop()
    while sys.stdin.readable():
        if line := await loop.run_in_executor(None, sys.stdin.readline):
            yield line


if __name__ == '__main__':
    lan_ip = net.base.hostname2ip()
    remote_rigs = Auxiliaries({'cameras': str(lan_ip) + ':99998', 'timeline': '192.168.1.236:99998'})
    alyx = AlyxClient()
    alyx.authenticate('miles')
    assert alyx.is_logged_in
    r = remote_rigs.push('ALYX', alyx, wait=True)
    r = remote_rigs.push('EXPINFO', dict(subject='subject'), wait=True)
    # assert sum(x[-1]['main_sync'] for x in r.values()), 'one main sync expected'
    #
    #
    # while remote_rigs.started is False:
    #     time.sleep(1)
    # assert remote_rigs.started is True

    # Thread(target = func2).start()
    # send a token
    """
    [net.base.ExpMessage.ALYX, alyx.base_url, {alyx.user: alyx._token}]
    """
