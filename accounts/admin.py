from django.contrib import admin
from accounts.models import UserProfile
from accounts.models import Clauses, Document
# Register your models here.
admin.site.register(UserProfile)
admin.site.register(Clauses)
admin.site.register(Document)
