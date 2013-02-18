import djangoappengine.main

from django.db.models.sql.query import Query

from mapreduce.input_readers import AbstractDatastoreInputReader
from mapreduce import util
from google.appengine.datastore import datastore_query

class DjangoKeyInputReader(AbstractDatastoreInputReader):
  """An input reader that takes a Django model ('app.models.Model') and yields Keys for that model"""

  def _iter_key_range(self, k_range):
    query = Query(util.for_name(self._entity_kind)).get_compiler(using="default").build_query()
    raw_entity_kind = query.db_table

    query = k_range.make_ascending_datastore_query(raw_entity_kind, keys_only=True)
    for key in query.Run(
        config=datastore_query.QueryOptions(batch_size=self._batch_size)):
      yield key, key 

class DjangoEntityInputReader(AbstractDatastoreInputReader):
  """An input reader that takes a Django model ('app.models.Model') and yields entities for that model"""

  def _iter_key_range(self, k_range):
    query = Query(util.for_name(self._entity_kind)).get_compiler(using="default").build_query()
    raw_entity_kind = query.db_table

    query = k_range.make_ascending_datastore_query(raw_entity_kind)
    for entity in query.Run(
        config=datastore_query.QueryOptions(batch_size=self._batch_size)):
      yield entity.key(), entity 
