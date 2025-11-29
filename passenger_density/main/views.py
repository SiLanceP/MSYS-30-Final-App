from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
import datetime
import numpy as np
import pandas as pd

from .models import Account, Station, train as Train, Historicalrecord

from .data import TrainNode, Queue, merge_sort, merge, linear_search

# Create your views here.

# --- 1. SIMULATION VIEW (Queue Logic + Time Calculation) ---
def station_monitor(request, station_name):
    station = get_object_or_404(Station, name=station_name)
    
    # Rebuild Queue from DB to simulate real-time queue
    # We order by 'last_updated' to maintain the correct sequence
    db_trains = Train.objects.filter(current_station=station).order_by('last_updated')
    station_queue = Queue() 
    for t in db_trains:
        station_queue.push(t.train_id)

    # --- TIME CALCULATION FEATURE ---
    # Logic: Start at 'now'. Each subsequent train arrives +12 minutes later.
    queue_display_items = []
    simulated_time = datetime.datetime.now()
    
    # Get all IDs from the queue structure
    all_train_ids = station_queue.get_all_items()
    
    for t_id in all_train_ids:
        try:
            t_obj = Train.objects.get(train_id=t_id)
            # Add temporary attribute for display (not saved to DB)
            t_obj.arrival_time_display = simulated_time.strftime("%H:%M")
            queue_display_items.append(t_obj)
            
            # Increment for the next train in line
            simulated_time += datetime.timedelta(minutes=12)
        except Train.DoesNotExist:
            continue

    context = {
        'station': station,
        'queue_items': queue_display_items, # Passing objects with times, not just IDs
        'current_train': None,
        'next_train': None
    }
    
    # Set Current and Next Train for the specific UI display boxes
    if queue_display_items:
        # The first item is the Current Train
        context['current_train'] = queue_display_items[0]
        
        # The second item (if it exists) is the Next Train
        if len(queue_display_items) > 1:
            context['next_train'] = queue_display_items[1]

    return render(request, 'station_monitor.html', context)

# --- 2. TRAIN DEPARTURE (Pop Logic) ---
def train_departure(request, station_name):
    station = get_object_or_404(Station, name=station_name)
    
    # Rebuild Queue to ensure we pop the correct train (First In, First Out)
    db_trains = Train.objects.filter(current_station=station).order_by('last_updated')
    station_queue = Queue()
    for t in db_trains:
        station_queue.push(t.train_id)

    arrived_train_id = station_queue.pop()
    
    if arrived_train_id:
        train_obj = Train.objects.get(train_id=arrived_train_id)
        
        # Log History before removing the train from the station
        Historicalrecord.objects.create(
            train=train_obj,
            station=station,
            passenger_count=train_obj.current_capacity,
            capacity_level=train_obj.capacity_level,
            timestamp=timezone.now()
        )
        
        # Remove from station (Simulates departure)
        train_obj.current_station = None 
        train_obj.save()

    return redirect('station_monitor', station_name=station_name)

# --- 3. REPORT VIEW (Daily & Weekly Analysis) ---
def report_dashboard(request, station_name):
    station = get_object_or_404(Station, name=station_name)
    
    # --- A. DAILY REPORT (Sorted by Merge Sort) ---
    today = timezone.now().date()
    daily_logs = Historicalrecord.objects.filter(station=station, timestamp__date=today)
    
    # Convert QuerySet to list for manual sorting
    daily_list = list(daily_logs)
    
    # ALGORITHM: MERGE SORT (Sort logs by passenger_count High -> Low)
    # Note: We reverse the sort to get Highest first
    sorted_daily = merge_sort(daily_list, key_func=lambda x: x.passenger_count)
    sorted_daily.reverse() 
    
    # ALGORITHM: LINEAR SEARCH (Filter by Train ID if user searches)
    search_query = request.GET.get('q', '')
    if search_query:
        sorted_daily = linear_search(sorted_daily, search_query, attribute_func=lambda x: x.train.train_id)

    # Determine Peak Time (First item after sort)
    peak_log = sorted_daily[0] if sorted_daily else None

    # --- B. WEEKLY REPORT (Sorted by Merge Sort) ---
    all_logs = Historicalrecord.objects.filter(station=station)
    
    # Aggregate using manual dictionary to prepare for Merge Sort
    day_buckets = {}
    for log in all_logs:
        day = log.date_str
        if day not in day_buckets:
            day_buckets[day] = []
        day_buckets[day].append(log.passenger_count)
    
    weekly_data = []
    for day, counts in day_buckets.items():
        avg = np.mean(counts) # using numpy
        weekly_data.append({'day': day, 'average': avg})
        
    # ALGORITHM: MERGE SORT (Sort days by Average Capacity High -> Low)
    sorted_weekly = merge_sort(weekly_data, key_func=lambda x: x['average'])
    sorted_weekly.reverse() # Highest average first
    
    peak_day = sorted_weekly[0] if sorted_weekly else None

    context = {
        'station': station,
        'daily_logs': sorted_daily, # Sorted High->Low
        'weekly_report': sorted_weekly, # Sorted High->Low
        'peak_log': peak_log,
        'peak_day': peak_day,
        'search_query': search_query
    }
    return render(request, 'report_dashboard.html', context)

# --- 4. EXCEL DOWNLOAD (Using Pandas + Merge Sort) ---
def download_excel_report(request, station_name):
    station = get_object_or_404(Station, name=station_name)
    all_logs = Historicalrecord.objects.filter(station=station)
    
    # 1. Prepare Data for Weekly Analysis
    data = []
    for log in all_logs:
        data.append({
            'Day': log.date_str,
            'Passenger Count': log.passenger_count,
            'Max Capacity': log.train.max_capacity,
            'Time': log.time_str,
            'Train ID': log.train.train_id
        })
    
    df = pd.DataFrame(data)
    
    if df.empty:
        return HttpResponse("No data available to download.")

    # Group by Day and get Mean
    weekly_summary = df.groupby('Day')[['Passenger Count', 'Max Capacity']].mean().reset_index()
    weekly_summary.columns = ['Day of Week', 'Average Passengers', 'Average Max Capacity']
    
    # 2. ALGORITHM: MERGE SORT (Sorting the Pandas results manually per requirement)
    summary_list = weekly_summary.to_dict('records')
    sorted_summary = merge_sort(summary_list, key_func=lambda x: x['Average Passengers'])
    sorted_summary.reverse() # High to Low
    
    # Convert back to DataFrame for Export
    final_df = pd.DataFrame(sorted_summary)
    
    # Add Status Column
    final_df['Status'] = final_df.apply(
        lambda row: "High" if (row['Average Passengers'] / row['Average Max Capacity']) >= 0.8 
               else "Medium" if (row['Average Passengers'] / row['Average Max Capacity']) >= 0.5 
               else "Low", axis=1
    )

    # 3. Create Response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    timestamp = timezone.now().strftime("%Y%m%d")
    response['Content-Disposition'] = f'attachment; filename="{station_name}_Weekly_Report_{timestamp}.xlsx"'
    
    # Write to Excel
    final_df.to_excel(response, index=False)
    
    return response