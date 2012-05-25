from django.test import TestCase
from django.utils import unittest
from django.db import models

from djangoappengine.fields import DbKeyField

from djangoappengine.db.models.manager import Manager

#from djangotoolbox.fields import ListField
#from google.appengine.api.datastore import Key

class ParentFoo(models.Model):
    key = DbKeyField(primary_key=True)
    foo = models.IntegerField()
    objects = Manager()

class ChildFoo(models.Model):
    key = DbKeyField(primary_key=True, parent_key_name='parent_key')
    foo = models.IntegerField()
    objects = Manager()
    
class AncestorTest(TestCase):
    def test_simple(self):
        px = ParentFoo(foo=5)
        px.save()
        px = ParentFoo(foo=2)
        px.save()
               
        parents = ParentFoo.objects.all()
        self.assertEqual(2, parents.count())
        
        parents = ParentFoo.objects.filter(foo=2)
        self.assertEqual(1, parents.count())
        
        child = ChildFoo(foo=10, parent_key=px.pk)
        orig_child_pk = child.pk
        child.save()

        results = list(ChildFoo.objects.ancestor(px.pk))

        self.assertEquals(1, len(results))
        self.assertEquals(results[0].pk, child.pk)
        
        results = list(ChildFoo.objects.all().ancestor(px.pk))

        self.assertEquals(1, len(results))
        self.assertEquals(results[0].pk, child.pk)