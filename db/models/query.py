from django.db.models.query import QuerySet as _baseQuerySet
from djangoappengine.db.utils import as_ancestor

class QuerySet(_baseQuerySet):
    def ancestor(self, ancestor):
        """
        Returns a new QuerySet instance with the args ANDed to the existing
        set.
        """      
        return self._filter_or_exclude(False, pk=as_ancestor(ancestor))
    
class EmptyQuerySet(QuerySet):
    def ancestor(self, *args, **kwargs):
        """
        Always returns EmptyQuerySet.
        """
        return self