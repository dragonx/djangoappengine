from django.db.models.query import QuerySet as _baseQuerySet

class QuerySet(_baseQuerySet):
    def ancestor(self, *args, **kwargs):
        """
        Returns a new QuerySet instance with the args ANDed to the existing
        set.
        """
        return self._filter_or_exclude(False, *args, **kwargs)
    
class EmptyQuerySet(QuerySet):
    def ancestor(self, *args, **kwargs):
        """
        Always returns EmptyQuerySet.
        """
        return self