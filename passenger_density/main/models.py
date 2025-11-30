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
    max_capacity = models.IntegerField(default=1600)  # max capacity of LRT2 train
    current_capacity = models.IntegerField(default=0)
    current_station = models.ForeignKey(Station, on_delete=models.SET_NULL, null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        station_name = self.current_station.name if self.current_station else "No station"
        return f"{self.train_id}: {self.current_capacity}/{self.max_capacity} at {station_name} (Last updated: {self.last_updated})"

    @property
    def capacity_level(self):
        if self.current_capacity <= 0:
            return "Empty"
        
        density = self.current_capacity / self.max_capacity
        if density >= 0.8:
            return "High"
        elif density >= 0.5:
            return "Medium"
        else:
            return "Low"

    def save(self, *args, **kwargs):
        """
        Log a Historicalrecord whenever passenger capacity (and thus density)
        changes for this train, at whatever station it is currently at.
        """
        # ensure capacity is within bounds (no negative or over max)
        if self.current_capacity < 0:
            self.current_capacity = 0
        if self.current_capacity > self.max_capacity:
            self.current_capacity = self.max_capacity

        # Get previous values
        old_capacity = None
        old_level = None
        old_station = None

        if self.pk is not None:
            try:
                old = train.objects.get(pk=self.pk)
                old_capacity = old.current_capacity
                old_level = old.capacity_level
                old_station = old.current_station
            except train.DoesNotExist:
                pass

        # Save train first
        super().save(*args, **kwargs)

        # Only log if the train is assigned to a station
        if not self.current_station:
            return

        # Decide if something relevant changed
        capacity_changed = (old_capacity is None) or (self.current_capacity != old_capacity)
        level_changed = (old_level is None) or (self.capacity_level != old_level)
        station_changed = (old_station is None) or (self.current_station != old_station)

        if capacity_changed or level_changed or station_changed:
            Historicalrecord.objects.create(
                train=self,
                station=self.current_station,
                timestamp=timezone.now(),
                passenger_count=self.current_capacity,
                capacity_level=self.capacity_level,
            )

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
