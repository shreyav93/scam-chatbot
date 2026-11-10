from django.db import models

class Source(models.Model):
    title = models.CharField(max_length=300)
    publisher = models.CharField(max_length=100)
    url = models.URLField(unique=True)
    category = models.CharField(max_length=50, blank=True)   # e.g. "impersonation"
    channel = models.CharField(max_length=30, blank=True)    # phone / email / text / any
    last_reviewed = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    content_hash = models.CharField(max_length=64, blank=True)
    last_ingested = models.DateTimeField(null=True, blank=True)

class Chunk(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="chunks")
    position = models.PositiveIntegerField()
    text = models.TextField()
    embedding = models.JSONField()

class UsageCounter(models.Model):
    key = models.CharField(max_length=100, unique=True)
    count = models.PositiveIntegerField(default=0)