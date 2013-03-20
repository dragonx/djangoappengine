import os
import errno
import types
import threading
import httplib
import socket
import select
from django.db import connections
from django.test import TestCase, TransactionTestCase

from google.appengine.datastore import datastore_stub_util

from db.stubs import stub_manager
from utils import appid
from unittest.runner import TextTestResult

from boot import devappserver_ver

class GAETestCase(TestCase):
    '''
    This base class configures the dev_appserver datastore to test for eventual consistency behavior.
    '''
    def _pre_setup(self):
        """Performs any pre-test setup.
            * Set the dev_appserver consistency state.
        """
        super(GAETestCase,self)._pre_setup()

        if hasattr(self, 'consistency_probability'):
            datastore = stub_manager.testbed.get_stub('datastore_v3')
            self._orig_policy = datastore._consistency_policy
            
            datastore.SetConsistencyPolicy(datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=self.consistency_probability))
        
    def _post_teardown(self):
        """ Performs any post-test things. This includes:

            * Putting back the original ROOT_URLCONF if it was changed.
            * Force closing the connection, so that the next test gets
              a clean cursor.
        """
        if hasattr(self, '_orig_policy'):
            datastore = stub_manager.testbed.get_stub('datastore_v3')
            datastore.SetConsistencyPolicy(self._orig_policy)

        super(GAETestCase,self)._post_teardown()

liveServerLock = threading.Lock()

class SyncTextTestResult(TextTestResult):
    def addError(self, test, err):
        if hasattr(test, "server_thread"):
            test.server_thread.join()
        super(SyncTextTestResult, self).addError(test, err)

if devappserver_ver == 1:
    from google.appengine.tools import dev_appserver
    from google.appengine.tools import dev_appserver_main

    class LiveServerThread(threading.Thread):
        """
        Thread for running a live http server while the tests are running.

        This is mostly copied from django.test.testcases.LiveServerThread
        It's modified slightly to launch dev_appserver instead of a plain
        HTTP server.  The shutdown mechanism is slightly different too.

        One big problem is that dev_appserver mangles the environment.
        It's easy to run into threading issues where the dev_appserver
        thread and the main application (test) thread conflict.  One common
        example is trying to use logging.error(), which will often cause
        conflicts since dev_appserver replaces stderr.  We use
        liveServerLock to avoid these conflicts.

        Your own test code will need to acquire liveServerLock pretty much
        every time you're doing something outside of an HTTP request.
        """

        def __init__(self, host, possible_ports, connections_override=None):
            self.host = host
            self.port = None
            self.possible_ports = possible_ports
            self.is_ready = threading.Event()
            self.error = None
            self.connections_override = connections_override
            super(LiveServerThread, self).__init__()

        def run(self):
            """
            Sets up the live server and databases, and then loops over handling
            http requests.
            """

            def sync_handle_request(self):
                try:
                    readable, _, _ = select.select([self.socket], [], [], 10)
                    if readable:
                        liveServerLock.acquire()
                        try:
                            self.original_handle_request()
                        except Exception, e:
                            pass
                        finally:
                            liveServerLock.release()
                except Exception, e:
                    pass

            if self.connections_override:
                from django.db import connections
                # Override this thread's database connections with the ones
                # provided by the main thread.
                for alias, conn in self.connections_override.items():
                    connections[alias] = conn
            try:
                # Go through the list of possible ports, hoping that we can find
                # one that is free to use for the WSGI server.
                for index, port in enumerate(self.possible_ports):
                    try:
                        options = dev_appserver_main.DEFAULT_ARGS.copy()
                        options['disable_task_running'] = True # Prevent launch of task queue thread
                        dev_appserver.SetupStubs(appid, **options)

                        self.httpd = dev_appserver.CreateServer(".", '/_ah/login', port, default_partition="dev")
                    except socket.error, e:
                        error_code = e.errno
                        if (index + 1 < len(self.possible_ports) and
                            error_code == errno.EADDRINUSE):
                            # This port is already in use, so we go on and try with
                            # the next one in the list.
                            continue
                        else:
                            # Either none of the given ports are free or the error
                            # is something else than "Address already in use". So
                            # we let that error bubble up to the main thread.
                            raise

                    else:
                        # A free port was found.
                        self.port = port
                        break

                # HACK: The magic happens here.  We replace the http request handler
                # with our sync'd version
                self.httpd.original_handle_request = self.httpd.handle_request
                self.httpd.handle_request = types.MethodType(sync_handle_request, self.httpd)

                self.is_ready.set()           
                self.httpd.serve_forever()
            except Exception, e:
                self.error = e
                try:
                    self.httpd.server_close()
                except Exception, e:
                    pass
                self.is_ready.set()

        def join(self, timeout=None):
            if hasattr(self, 'httpd'):
                # Stop the WSGI server
                try:
                    self.httpd.stop_serving_forever()
                    # We need to hit the server with one more request to make it quit
                    connection = httplib.HTTPConnection(self.host, self.port)
                    connection.request('GET',"/")
                    connection.close()
                    #self.httpd.server_close()
                except Exception, e:
                    pass
            super(LiveServerThread, self).join(timeout)


    # This is copied directly from django.test.testcases
    class LiveServerTestCase(TransactionTestCase):
        """
        Does basically the same as TransactionTestCase but also launches a live
        http server in a separate thread so that the tests may use another testing
        framework, such as Selenium for example, instead of the built-in dummy
        client.

        Note that it inherits from TransactionTestCase instead of TestCase because
        the threads do not share the same transactions (unless if using in-memory
        sqlite) and each thread needs to commit all their transactions so that the
        other thread can see the changes.

        Be careful that almost everything you do needs to be synchronized against
        the liveServerLock (which you can easily reference as this.lock()
        """
        lock = liveServerLock

        @property
        def live_server_url(self):
            return 'http://%s:%s' % (
                self.server_thread.host, self.server_thread.port)

        def _pre_setup(self):
            connections_override = {}
            for conn in connections.all():
                # If using in-memory sqlite databases, pass the connections to
                # the server thread.
                if (conn.settings_dict['ENGINE'] == 'django.db.backends.sqlite3'
                    and conn.settings_dict['NAME'] == ':memory:'):
                    # Explicitly enable thread-shareability for this connection
                    conn.allow_thread_sharing = True
                    connections_override[conn.alias] = conn

            # Launch the live server's thread
            specified_address = os.environ.get(
                'DJANGO_LIVE_TEST_SERVER_ADDRESS', 'localhost:8081-8089')

            # The specified ports may be of the form '8000-8010,8080,9200-9300'
            # i.e. a comma-separated list of ports or ranges gg ports, so we break
            # it down into a detailed list of all possible ports.
            possible_ports = []
            try:
                host, port_ranges = specified_address.split(':')
                for port_range in port_ranges.split(','):
                    # A port range can be of either form: '8000' or '8000-8010'.
                    extremes = map(int, port_range.split('-'))
                    assert len(extremes) in [1, 2]
                    if len(extremes) == 1:
                        # Port range of the form '8000'
                        possible_ports.append(extremes[0])
                    else:
                        # Port range of the form '8000-8010'
                        for port in range(extremes[0], extremes[1] + 1):
                            possible_ports.append(port)
            except Exception:
                raise ImproperlyConfigured('Invalid address ("%s") for live '
                    'server.' % specified_address)

            self.server_thread = LiveServerThread(
                host, possible_ports, connections_override)
            self.server_thread.daemon = True
            self.server_thread.start()

            # Wait for the live server to be ready
            self.server_thread.is_ready.wait()
            if self.server_thread.error:
                raise self.server_thread.error

            liveServerLock.acquire() # Lock while we load fixtures
            super(LiveServerTestCase, self)._pre_setup()
            liveServerLock.release()

        def _post_teardown(self):
            # There may not be a 'server_thread' attribute if setUpClass() for some
            # reasons has raised an exception.
            if hasattr(self, 'server_thread'):
                # Terminate the live server's thread
                self.server_thread.join()
            super(LiveServerTestCase, self)._post_teardown()

else: # devappserver2
    import sys
    from django.db import DEFAULT_DB_ALIAS
    from django.core.management import call_command
    import dev_appserver
    from google.appengine.api import apiproxy_stub_map
    from google.appengine.tools.devappserver2 import devappserver2
    from google.appengine.tools.devappserver2 import python_runtime
    from google.appengine.tools.devappserver2 import shutdown

    sys.path[1:1] = dev_appserver._DEVAPPSERVER2_PATHS

    class LiveServerTestCase(TransactionTestCase):
        """
        Does basically the same as TransactionTestCase but also launches a live
        http server in a separate thread so that the tests may use another testing
        framework, such as Selenium for example, instead of the built-in dummy
        client.

        Note that it inherits from TransactionTestCase instead of TestCase because
        the threads do not share the same transactions (unless if using in-memory
        sqlite) and each thread needs to commit all their transactions so that the
        other thread can see the changes.

        Be careful that almost everything you do needs to be synchronized against
        the liveServerLock (which you can easily reference as this.lock()
        """
        lock = liveServerLock

        @property
        def live_server_url(self):
            return 'http://%s:%s' % (
                'localhost', self.port)

        def _pre_setup(self):
            apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
            self.server = None

            # Launch the live server's thread
            specified_address = os.environ.get(
                'DJANGO_LIVE_TEST_SERVER_ADDRESS', 'localhost:8081-8089')

            # The specified ports may be of the form '8000-8010,8080,9200-9300'
            # i.e. a comma-separated list of ports or ranges gg ports, so we break
            # it down into a detailed list of all possible ports.
            possible_ports = []
            try:
                host, port_ranges = specified_address.split(':')
                for port_range in port_ranges.split(','):
                    # A port range can be of either form: '8000' or '8000-8010'.
                    extremes = map(int, port_range.split('-'))
                    assert len(extremes) in [1, 2]
                    if len(extremes) == 1:
                        # Port range of the form '8000'
                        possible_ports.append(extremes[0])
                    else:
                        # Port range of the form '8000-8010'
                        for port in range(extremes[0], extremes[1] + 1):
                            possible_ports.append(port)
            except Exception:
                raise ImproperlyConfigured('Invalid address ("%s") for live '
                    'server.' % specified_address)

            python_runtime._RUNTIME_ARGS = [
                sys.executable,
                os.path.join(
                    os.path.dirname(dev_appserver.__file__), '_python_runtime.py')]
            options = devappserver2.PARSER.parse_args([
                '--admin_port', '0',
                '--port', '%s' % possible_ports[0],
                '--datastore_path', ':memory:',
                '--logs_path', ':memory:',
                '--skip_sdk_update_check',
                '--',
                '.'])
            self.port = possible_ports[0]
            self.server = devappserver2.DevelopmentServer()
            self.server.start(options)
            
            # Wait for the live server to be ready
            # How do we sync this?

            liveServerLock.acquire() # Lock while we load fixtures
            super(LiveServerTestCase, self)._pre_setup()
            liveServerLock.release()

        def _fixture_setup(self):
            # If the test case has a multi_db=True flag, flush all databases.
            # Otherwise, just flush default.
            if getattr(self, 'multi_db', False):
                databases = connections
            else:
                databases = [DEFAULT_DB_ALIAS]
            try:
                for db in databases:
                    # call_command('flush', verbosity=0, interactive=False, database=db)

                    if hasattr(self, 'fixtures'):
                        # We have to use this slightly awkward syntax due to the fact
                        # that we're using *args and **kwargs together.
                        call_command('loaddata', *self.fixtures,
                                     **{'verbosity': 0, 'database': db})
            except Exception, e:
                pass

        def _post_teardown(self):
            if self.server:
                print 'Stopping server'
                self.server.stop()
                print 'Server stopped'
                import eat
                eat.gaebp()

            super(LiveServerTestCase, self)._post_teardown()

