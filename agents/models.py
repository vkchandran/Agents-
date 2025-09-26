from django.db import models
from django.contrib.auth.models import BaseUserManager,AbstractBaseUser,PermissionsMixin
import uuid

# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self,email,password=None,**extrafields):
        if not email:
            raise ValueError("email field mus be set")
        user = self.model(email=email,**extrafields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_superuser(self,email,password=None,**extrafields):
        extrafields.setdefault("is_active",True)
        extrafields.setdefault("is_staff",True)
        extrafields.setdefault("is_superuser",True)
        if extrafields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extrafields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self.create_user(email,password,**extrafields)
   
class CustomUser(AbstractBaseUser,PermissionsMixin):
    uuid = models.UUIDField(default=uuid.uuid4,editable=False,unique=True)
    first_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
   
    objects = UserManager()


    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['first_name']


    def __str__(self):
        return super().__str__()
    
    
class AgentsApp(models.Model):
    name = models.CharField(max_length=100)
    url_name = models.CharField(max_length=100)
    type = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    status = models.CharField(max_length=100)