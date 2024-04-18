"""
Network communication between rigs.

An example of a remote_rigs.yaml file:

```yaml
neuropixel: '12.134.270.1'
'cameras:left': 'tcp://0.123.456.7:9998'
'cameras:right': 'tcp://0.123.456.6:9998'
tasks: 'udp://123.654.8.8'
```

Goal: run iblutil net services synchronously using threads
https://stackoverflow.com/questions/59645272/how-do-i-pass-an-async-function-to-a-thread-target-in-python#61778654
https://docs.python.org/3.11/library/threading.html#event-objects
https://stackoverflow.com/questions/51242467/communicate-data-between-threads-in-python
https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor
https://journal.stuffwithstuff.com/2015/02/01/what-color-is-your-function/
"""
import asyncio
import threading
# from threading import Thread
import time

from iblutil.io import net
from iblutil.util import setup_logger

log = setup_logger('iblrig.net', level=10)


class Singleton(type):
    """A singleton class."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """Ensure the same instance is returned."""
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Auxiliaries(metaclass=Singleton):
    services = None
    connected = False
    started = False
    waiting = False
    _remote_rigs = []
    _queued: dict[float, list] = {}
    _log: dict[float, dict] = {}

    def __new__(cls, *args, **kwargs):
        # FIXME Is this necessary?
        cls.check = threading.Condition()
        return super().__new__(cls)

    def __init__(self, clients):
        """
        Connect to and communicate with one or more remote rigs.

        Parameters
        ----------
        clients : dict[str, str]
            A map of name to URI.
        """
        # Load clients
        self._clients = clients or {}

    async def create(self):
        self._remote_rigs = [await net.app.EchoProtocol.client(uri, name) for name, uri in self._clients.items()]
        self.services = net.app.Services(self._remote_rigs, timeout=10)
        log.debug('Connected...')
        self.connected = True
        # Assign a callback to all clients
        callback = lambda _, addr: print('{}:{} started'.format(*addr))
        self.services.assign_callback('EXPSTART', callback)

    async def start(self):
        responses = await self.services.start('2022-01-01_1_subject', concurrent=False)
        self.started = True

    async def listen(self, refresh_rate=0.2):
        """This should be called from another thread.
        TODO Handle cleanup; disconnect before thread destroyed
        """
        await self.create()
        while True:
            if any(queue := sorted(self._queued)):
                request_time = queue[0]
                t_str = time.strftime('%H:%M:%S', time.localtime(request_time))
                event, args, kwargs = self._queued[request_time]
                if not isinstance(event, net.base.ExpMessage):
                    raise TypeError('invalid message cued at ' + t_str)
                log.debug('Sending %s message requested at %s', event.name, t_str)
                match event:
                    case net.base.ExpMessage.EXPSTART:
                        exp_ref, data = args
                        responses = await self.services.start(exp_ref, data)
                    case net.base.ExpMessage.EXPINFO:
                        # TODO Instead of waiting for all responses, cancel futures when main sync responds?
                        responses = await self.services._signal(event, 'confirmed_send', [event, *args])
                    case _:
                        raise NotImplementedError
                self._log[request_time] = responses
                self._queued.pop(request_time)
            await asyncio.sleep(refresh_rate)

    def send(self, message: net.base.ExpMessage, *args, wait=False, **kwargs):
        # TODO Handle timeouts
        request_time = time.time()
        from one.util import ensure_list
        self._queued[request_time] = [net.base.ExpMessage.validate(message), ensure_list(args), kwargs]
        refresh_rate = .2 if wait is True else float(wait)
        while wait and request_time in self._queued:
            time.sleep(refresh_rate)
        return self._log[request_time] if wait else request_time



# Assign a callback to all clients
# callback = lambda _, addr: print('{}:{} finished clean up'.format(*addr))
# services.assign_callback('EXPCLEANUP', callback)
#
# # Remove this callback
# services.clear_callbacks('EXPCLEANUP', callback)
#
# # Assign callback that receives client instance
# callback = lambda *_, rig: print(f'{rig.name} finished clean up')
# services.assign_callback('EXPCLEANUP', callback, return_service=True)




# def func1():
#     print ("funn1 started")
#     check.acquire()
#     check.wait()
#     print ("got permission")
#     print ("funn1 finished")
#
#
# def func2():
#     print ("func2 started")
#     check.acquire()
#     time.sleep(2)
#     check.notify()
#     check.release()
#     time.sleep(2)
#     print ("func2 finished")


if __name__ == '__main__':
    lan_ip = net.base.hostname2ip()
    remote_rigs = Auxiliaries({'client_1': str(lan_ip) + ':9998'})
    # Thread(target=remote_rigs.create).start()
    _thread = threading.Thread(target=asyncio.run, args=(remote_rigs.listen(),))
    _thread.start()
    r = remote_rigs.send('EXPINFO', dict(subject='subject'), wait=True)
    assert sum(x[-1]['main_sync'] for x in r.values()), 'one main sync expected'


    while remote_rigs.started is False:
        time.sleep(1)
    assert remote_rigs.started is True

    # Thread(target = func2).start()
