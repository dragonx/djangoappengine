from django.test import TestCase
from django.utils import unittest
from django.db import models

#from djangoappengine.fields import DbKeyField
#from djangoappengine.db.utils import as_ancestor

from djangoappengine.db.models.manager import Manager

#from djangotoolbox.fields import ListField
#from google.appengine.api.datastore import Key


class ParentFoo(models.Model):
    foo = models.IntegerField()
    objects = Manager()

class ChildModel(models.Model):
    data = models.IntegerField()
    #objects = Manager()
    
class AncestorTest(TestCase):
    def test_simple(self):
        px = ParentFoo(foo=5)
        px.save()
        px = ParentFoo(foo=2)
        px.save()
        
        import eat
        eat.gaebp(True)
        
        parents = ParentFoo.objects.all()
        self.assertEqual(2, parents.count())
        
        parents = ParentFoo.objects.ancestor(foo=2)
        self.assertEqual(1, parents.count())