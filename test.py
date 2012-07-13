import os
import threading
import httplib          
from django.core.handlers.wsgi import WSGIHandler
from django.core.servers.basehttp import WSGIServerException
from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.test.testcases import _MediaFilesHandler
from django.contrib.staticfiles.handlers import StaticFilesHandler

from google.appengine.tools import dev_appserver
from google.appengine.tools import dev_appserver_main
from google.appengine.datastore import datastore_stub_util

from db.stubs import stub_manager

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


class LiveServerThread(threading.Thread):
    """
    Thread for running a live http server while the tests are running.

    This is mostly copied from django.test.testcases.LiveServerThread
    It's modified slightly to launch dev_appserver instead of a plain
    HTTP server.  The shutdown mechanism is slightly different too.
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
        if self.connections_override:
            from django.db import connections
            # Override this thread's database connections with the ones
            # provided by the main thread.
            for alias, conn in self.connections_override.items():
                connections[alias] = conn
        try:
            # Create the handler for serving static and media files
            handler = StaticFilesHandler(_MediaFilesHandler(WSGIHandler()))

            # Go through the list of possible ports, hoping that we can find
            # one that is free to use for the WSGI server.
            for index, port in enumerate(self.possible_ports):
                try:
                    options = dev_appserver_main.DEFAULT_ARGS.copy()
                    dev_appserver.SetupStubs("project-eat", **options)
                    self.httpd = dev_appserver.CreateServer(".", '/_ah/login', port, default_partition="dev")

                except WSGIServerException, e:
                    if sys.version_info < (2, 6):
                        error_code = e.args[0].args[0]
                    else:
                        error_code = e.args[0].errno
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

            #self.httpd.set_app(handler)
            self.is_ready.set()           
            self.httpd.serve_forever()
        except Exception, e:
            self.error = e
            self.is_ready.set()

    def join(self, timeout=None):
        if hasattr(self, 'httpd'):
            # Stop the WSGI server
            self.httpd.stop_serving_forever()
            try:
                # We need to hit the server with one more request to make it quit
                connection = httplib.HTTPConnection(self.host, self.port)
                connection.request('GET',"/")
            except:
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
    """

    @property
    def live_server_url(self):
        return 'http://%s:%s' % (
            self.server_thread.host, self.server_thread.port)

    @classmethod
    def setUpClass(cls):
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
            'DJANGO_LIVE_TEST_SERVER_ADDRESS', 'localhost:8081')

        # The specified ports may be of the form '8000-8010,8080,9200-9300'
        # i.e. a comma-separated list of ports or ranges of ports, so we break
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
        cls.server_thread = LiveServerThread(
            host, possible_ports, connections_override)
        cls.server_thread.daemon = True
        cls.server_thread.start()

        # Wait for the live server to be ready
        cls.server_thread.is_ready.wait()
        if cls.server_thread.error:
            raise cls.server_thread.error

        super(LiveServerTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        # There may not be a 'server_thread' attribute if setUpClass() for some
        # reasons has raised an exception.
        if hasattr(cls, 'server_thread'):
            # Terminate the live server's thread
            cls.server_thread.join()
        super(LiveServerTestCase, cls).tearDownClass()

