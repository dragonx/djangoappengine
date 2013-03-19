from django.core.management.commands.test import Command as OriginalCommand

from django.test import client

from google.appengine.api import files
from google.appengine.ext.blobstore import BlobInfo

original_encode_file = client.encode_file

def my_encode_file(boundary, key, file):
    # encode_file with blobstore support.
    # Expecting something like this in the test:

    '''
    from google.appengine.api import files
    fn = files.blobstore.create(mime_type="image/jpg", _blobinfo_uploaded_filename="foo.jpg")
    with files.open(fn, 'a') as fp:
        fp.write("bar")
    files.finalize(fn)

    with files.open(fn) as fp:
        response = self.client.post('/viewurl', {"fileparam" : fp})
    '''
    if hasattr(file, "_filename"):
        blob_key = files.blobstore.get_blob_key(file._filename)
        blobinfo = BlobInfo.get(blob_key)
        return [
            '--' + boundary,
            'Content-Type: message/external-body; blob-key=%s; access-type="X-AppEngine-BlobKey"' % blob_key,
            'MIME-Version: 1.0',
            'Content-Disposition: form-data; name="%s"; filename="%s"' % (key, blobinfo.filename),
            '',
            'Content-Type: %s' % blobinfo.content_type
        ]
    else:
        return original_encode_file(boundary, key, file)

class Command(OriginalCommand):
    def __init__(self):
        # monkey patch client's encode_file with our own
        # with blobstore support
        client.encode_file = my_encode_file
        super(Command, self).__init__()
