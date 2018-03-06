from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField


class Author(models.Model):
    name = models.CharField(max_length=120)


class Color(models.Model):
    title = models.CharField(max_length=20)


class Book(models.Model):
    title = models.CharField(max_length=120)
    authors = models.ManyToManyField(Author, related_name='books')
    color = models.ForeignKey(Color, related_name='books', on_delete=models.PROTECT)  # noqa
    json_data = JSONField()
    array_data = ArrayField(models.CharField(max_length=2))
