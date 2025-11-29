from django.db import models
from django.utils import timezone

# Create your models here.
class Account(models.Model):
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=100)

    def getUsername(self):
        return self.username
    def getPassword(self):
        return self.password
    def __str__(self):
        return f"Account: {self.username}"

class Station(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.IntegerField(default=0)
    
    def __str__(self):
        return self.name

class train(models.Model):
    train_id = models.IntegerField(unique=True)
    max_capacity = models.IntegerField(default=1600) #the max capacity of the lrt2 train (both standing and sitting)
    current_capacity = models.IntegerField(default=0)
    current_station = models.ForeignKey(Station, on_delete=models.SET_NULL, null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.train_id}: {self.current_capacity}/{self.max_capacity} at {self.current_station.name} (Last updated: {self.last_updated})"
    
    @property
    def capacity_level(self):
        density = self.current_capacity / self.max_capacity
        if density >= 0.8: return "High"
        elif density >= 0.5: return "Medium"
        else: return "Low"

class Historicalrecord(models.Model):
    train = models.ForeignKey(train, on_delete=models.CASCADE)
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    passenger_count = models.IntegerField(default=0)
    capacity_level = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.train.train_id} ({self.timestamp.strftime('%H:%M')})"
    
    @property
    # helper function for daily reports
    def time_str(self):
        return self.timestamp.strftime('%I:%M %p')
    
    @property
    # helper function for weekly reports
    def date_str(self):
        return self.timestamp.strftime('%A')
    
