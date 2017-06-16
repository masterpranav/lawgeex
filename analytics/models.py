from __future__ import unicode_literals

from django.db import models
from shortener.models import PcURL

class ClickEventManager(models.Manager):
	def create_event(self,pcInstance):
		if isinstance(pcInstance,PcURL):
			obj,created=self.get_or_create(pc_url=pcInstance)
			obj.count+=1
			obj.save()
			return obj.count
		return None

class ClickEvent(models.Model):
	pc_url = models.OneToOneField(PcURL)
	count = models.IntegerField(default=0)
	updated=models.DateTimeField(auto_now=True)
	timestamp=models.DateTimeField(auto_now_add=True)

	objects=ClickEventManager()

	def __str__(self):
		return "{i}".format(i =self.count)			