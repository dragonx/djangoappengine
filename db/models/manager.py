from django.db.models import Manager as _baseManager

class Manager(_baseManager):
    def ancestor(self, *args, **kwargs):
        return self.get_query_set().filter(*args, **kwargs)