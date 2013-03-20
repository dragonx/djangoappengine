from django.core.management.commands.shell import Command as ShellCommand
from ...boot import devappserver_ver

class Command(ShellCommand):
    def __init__(self):
        super(Command, self).__init__()
        if devappserver_ver == 2:
            # This setup is usually done in devappserver2.DevelopmentServer
            # We don't want to run the full server when we just need the shell
            # Just use the code to setup the datastore stubs.
            import os
            import time
            from google.appengine.datastore import datastore_stub_util
            from google.appengine.tools.devappserver2 import api_server
            from google.appengine.tools.devappserver2 import application_configuration

            # Mimic google.appengine.tools.devappserver2
            os.environ['TZ'] = 'UTC'
            if hasattr(time, 'tzset'):
                # time.tzet() should be called on Unix, but doesn't exist on Windows.
                time.tzset()

            from google.appengine.tools.devappserver2.devappserver2 import PARSER, _get_storage_path, _setup_environ
            options = PARSER.parse_args(['--admin_port', '0',
                                         '--port', '0',
                                         '--datastore_path', '.gaedata/datastore',
                                         '--logs_path', ':memory',
                                         '--skip_sdk_update_check', "yes",
                                         "."])

            configuration = application_configuration.ApplicationConfiguration(
                            options.yaml_files)

            _setup_environ(configuration.app_id)

            storage_path = _get_storage_path(options.storage_path, configuration.app_id)
            datastore_path = options.datastore_path or os.path.join(storage_path,
                                                                    'datastore.db')
            logs_path = options.logs_path or os.path.join(storage_path, 'logs.db')

            search_index_path = options.search_indexes_path or os.path.join(
                storage_path, 'search_indexes')

            prospective_search_path = options.prospective_search_path or os.path.join(
                storage_path, 'prospective-search')

            blobstore_path = options.blobstore_path or os.path.join(storage_path,
                                                                    'blobs')

            api_server.setup_stubs(
                request_data='',
                app_id=configuration.app_id,
                application_root=configuration.servers[0].application_root,
                # The "trusted" flag is only relevant for Google administrative
                # applications.
                trusted=getattr(options, 'trusted', False),
                blobstore_path=blobstore_path,
                datastore_path=datastore_path,
                datastore_consistency=datastore_stub_util.PseudoRandomHRConsistencyPolicy(1.0),
                datastore_require_indexes=options.require_indexes,
                datastore_auto_id_policy=options.auto_id_policy,
                images_host_prefix='',
                logs_path=logs_path,
                mail_smtp_host=options.smtp_host,
                mail_smtp_port=options.smtp_port,
                mail_smtp_user=options.smtp_user,
                mail_smtp_password=options.smtp_password,
                mail_enable_sendmail=options.enable_sendmail,
                mail_show_mail_body=options.show_mail_body,
                matcher_prospective_search_path=prospective_search_path,
                search_index_path=search_index_path,
                taskqueue_auto_run_tasks=options.enable_task_running,
                taskqueue_default_http_server='%s'%options.host,
                user_login_url='',
                user_logout_url='')
