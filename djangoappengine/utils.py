import os

from google.appengine.api import apiproxy_stub_map
from google.appengine.api.app_identity import get_application_id


have_appserver = bool(apiproxy_stub_map.apiproxy.GetStub('datastore_v3'))

if have_appserver:
    appid = get_application_id()
else:
    try:
        # Original dev_appserver method
        from google.appengine.tools import dev_appserver
        from .boot import PROJECT_DIR
        appconfig = dev_appserver.LoadAppConfig(PROJECT_DIR, {},
                                                default_partition='dev')[0]
        appid = appconfig.application.split('~', 1)[-1]
    except ImportError, e:
        try:
            from google.appengine.tools.devappserver2 import application_configuration
            configuration = application_configuration.ApplicationConfiguration(["app.yaml"])
            appid = configuration.app_id.split('~', 1)[-1]
            
        except Exception, e:
            raise Exception("Could not get appid. Is your app.yaml file missing? "
                            "Error was: %s" % e)

on_production_server = have_appserver and \
    not os.environ.get('SERVER_SOFTWARE', '').lower().startswith('devel')
