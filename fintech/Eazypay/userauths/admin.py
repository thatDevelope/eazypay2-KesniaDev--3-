from django.contrib import admin

# Register your models here.
from userauths.models import User


admin.site.register(User)