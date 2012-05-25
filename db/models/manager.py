from django.db.models import Manager as _baseManager
from djangoappengine.db.utils import as_ancestor
from djangoappengine.db.models.query import QuerySet

class Manager(_baseManager):
    
    def get_query_set(self):
        """Returns a new QuerySet object.  Subclasses can override this method
        to easily customize the behavior of the Manager.
        """
        return QuerySet(self.model, using=self._db)
    
    def ancestor(self, ancestor):
        return self.get_query_set().ancestor(ancestor)