from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model.

    Starting with a custom user model (even though it's currently a thin
    wrapper around AbstractUser) avoids the well-known Django pitfall of
    needing a disruptive migration if user-specific fields are needed
    later — swapping AUTH_USER_MODEL after the first migration is painful.
    """

    email = models.EmailField(unique=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username
