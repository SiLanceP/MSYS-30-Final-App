from django.contrib import admin
from .models import Account, Station, train, Historicalrecord
# Register your models here.
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('username',)
    search_fields = ('username',)

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    search_fields = ('name',)
    ordering = ('order',)

@admin.register(train)
class trainAdmin(admin.ModelAdmin):
    list_display = ('train_id', 'max_capacity', 'current_capacity', 'current_station', 'capacity_level', 'last_updated')
    search_fields = ('train_id',)
    list_filter = ('current_station', 'last_updated')
    ordering = ('train_id',)

    def capacity_level(self, obj):
        return obj.capacity_level
    capacity_level.short_description = 'Density Level'

@admin.register(Historicalrecord)
class HistoricalrecordAdmin(admin.ModelAdmin):
    list_display = ('train', 'station', 'timestamp', 'passenger_count', 'capacity_level', 'get_time', 'get_day')
    list_filter = ('station', 'timestamp', 'capacity_level')
    search_fields = ('train__train_id', 'station__name')
    ordering = ('-timestamp',)

    def get_time(self, obj):
        return obj.time_str
    get_time.short_description = 'Time'
    def get_day(self, obj):
        return obj.date_str
    get_day.short_description = 'Day'

    
