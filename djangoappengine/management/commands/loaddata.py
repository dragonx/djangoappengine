from django.core.management.commands.loaddata import Command as OriginalCommand

from google.appengine.api import apiproxy_stub_map
from google.appengine.datastore import datastore_stub_util

class Command(OriginalCommand):
    def handle(self, *fixture_labels, **options):
        retval = None
        # Temporarily change consistency policy to force apply loaded data
        datastore = apiproxy_stub_map.apiproxy.GetStub('datastore_v3')

        try:
            # datastore._consistency_policy only exists in dev_appserver
            # will throw exception in production
            orig_consistency_policy = datastore._consistency_policy
            datastore.SetConsistencyPolicy(datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1))
        except:
            orig_consistency_policy = None

        retval = super(Command, self).handle(*fixture_labels, **options)

        if orig_consistency_policy:
            datastore.SetConsistencyPolicy(orig_consistency_policy)

        return retval
