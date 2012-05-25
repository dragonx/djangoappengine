from django.test import TestCase

from google.appengine.datastore import datastore_stub_util

from db.stubs import stub_manager

class GAETestCase(TestCase):
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
