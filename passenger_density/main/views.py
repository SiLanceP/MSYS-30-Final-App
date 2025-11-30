from django.shortcuts import render, redirect, get_object_or_404
from collections import defaultdict
from io import BytesIO
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.urls import reverse
import datetime
import numpy as np
import pandas as pd
from .models import Account, Station, train as Train, Historicalrecord
from .data import TrainNode, Queue, merge_sort, merge, linear_search
import random

# Create your views here.
def get_density(train):
    """
    Returns the color class based on passenger density.
    Assumes train has 'passenger_count' and 'capacity'.
    """
    if not train:
        return 'none'
    
    # Calculate percentage (protect against divide by zero)
    if train.capacity == 0: 
        percentage = 0 
    else:
        percentage = (train.passenger_count / train.capacity) * 100

    if percentage >= 80:
        return 'high'   # Red
    elif percentage >= 50:
        return 'medium' # Yellow
    else:
        return 'low'    # Green
    
# --- 1. SIMULATION VIEW (Queue Logic + Time Calculation) ---
def home(request):
    # 1. Stations ordered like the railway map
    stations = Station.objects.order_by("order")

    station_rows = []
    for station in stations:
        queue = Train.objects.filter(current_station=station).order_by("last_updated")
        station_rows.append({
            "station": station,
            "queue": list(queue),
        })

    # 2. All trains for dropdown
    all_trains = list(Train.objects.all().order_by("train_id"))

    # 3. Use linear_search to find the selected train (if any)
    selected_train = None
    selected_station = None

    query = request.GET.get("train_id")  # value from dropdown
    if query:
        get_id_func = lambda t: str(t.train_id)
        matches = linear_search(all_trains, query, get_id_func)
        if matches:
            selected_train = matches[0]
            selected_station = selected_train.current_station

    context = {
        "station_rows": station_rows,
        "all_trains": all_trains,
        "selected_train": selected_train,
        "selected_station": selected_station,
    }
    return render(request, "passenger_density/home.html", context)

@require_POST
def advance_trains(request):
    stations = list(Station.objects.order_by('order'))
    if not stations:
        return redirect('home')

    now = timezone.now()

    # Work from last station backwards so we don't move a train twice
    for i in range(len(stations) - 1, -1, -1):
        station = stations[i]
        queue = list(Train.objects.filter(current_station=station).order_by('last_updated'))
        if not queue:
            continue

        front = queue[0]  # FIFO: first in line leaves this station

        # 1) Randomize passenger capacity (0 .. max_capacity)
        front.current_capacity = random.randint(0, front.max_capacity)

        # 2) Move to next station or remove from line at the last station
        if i == len(stations) - 1:
            # Last station: train leaves the line (no next station)
            front.current_station = None
        else:
            next_station = stations[i + 1]
            front.current_station = next_station

        # 3) Update timestamp for queue ordering
        front.last_updated = now

        # 4) Save — your train.save() override will log this change
        front.save()

    return redirect("home")

@require_POST
def reset_trains_to_start(request):
    first_station = Station.objects.order_by('order').first()
    if not first_station:
        return redirect('home')  # nothing to do if no stations

    # Order trains by ID so the queue is deterministic
    trains = Train.objects.all().order_by('train_id')
    now = timezone.now()

    for idx, t in enumerate(trains):
        t.current_station = first_station
        t.current_capacity = 0          # <<< reset passenger count here
        # Stagger last_updated slightly so FIFO is clear
        t.last_updated = now + datetime.timedelta(seconds=idx)
        t.save()

    return redirect('home')
@require_POST
def update_capacity(request, train_id):
    train = get_object_or_404(Train, pk=train_id)

    raw_value = request.POST.get("current_capacity")
    try:
        new_capacity = int(raw_value)
    except (TypeError, ValueError):
        return redirect("home")

    if new_capacity < 0:
        new_capacity = 0

    train.current_capacity = new_capacity
    train.save(update_fields=["current_capacity"])  # triggers your save() hook

    return redirect("home")

DENSITY_SCORE = {"empty": 0, "low": 1, "medium": 2, "high": 3}

def _build_daily_report_data(target_date):
    """Core data for the daily density report."""
    # Only consider logs at the last station
    qs = Historicalrecord.objects.select_related("train", "station") \
                                .filter(timestamp__date=target_date) \
                                .order_by("timestamp")
    logs = list(qs)

    # Which trains appear in the logs?
    train_ids = sorted({log.train.train_id for log in logs})
    trains = list(Train.objects.filter(train_id__in=train_ids).order_by("train_id"))

    # Time slots 6:00–18:00
    start_hour = 6
    end_hour = 18
    hours = list(range(start_hour, end_hour + 1))

    # grid[hour][train_id] = 'low' / 'medium' / 'high' / ''
    grid = {hour: {t.train_id: "" for t in trains} for hour in hours}

    for log in logs:
        local_ts = timezone.localtime(log.timestamp)
        hour = local_ts.hour
        if hour < start_hour or hour > end_hour:
            continue
        grid[hour][log.train.train_id] = log.capacity_level.lower()

    # Build rows for template (same structure as before)
    rows = []
    for hour in hours:
        # Use 12-hour format like "6:00 AM"
        label_time = datetime.time(hour=hour)
        label = label_time.strftime("%I:00 %p").lstrip("0")
        cells = [grid[hour][t.train_id] for t in trains]
        rows.append({"label": label, "cells": cells})

    return {
        "target_date": target_date,
        "logs": logs,
        "trains": trains,
        "rows": rows,
        "hours": hours,
    }

def daily_density_report(request):
    # 1) Date selection
    date_str = request.GET.get("date")
    if date_str:
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    # 2) Sort mode: 'time' (default), 'high', or 'low'
    sort_mode = request.GET.get("sort", "time")

    core = _build_daily_report_data(target_date)
    logs = core["logs"]
    trains = core["trains"]
    rows = core["rows"]

    # --- A) Per-train events sorted according to sort_mode ---
    per_train_sorted = []
    for t in trains:
        # logs are already ordered by timestamp in _build_daily_report_data
        t_logs = [log for log in logs if log.train.train_id == t.train_id]
        if not t_logs:
            continue

        if sort_mode in ("high", "low"):
            # Use merge_sort to sort by density score, then passenger_count
            def key_func(log):
                level = log.capacity_level.lower()
                score = DENSITY_SCORE.get(level, 0)
                return (score, log.passenger_count)

            sorted_logs = merge_sort(t_logs, key_func)  # highest score first
            if sort_mode == "low":
                sorted_logs = list(reversed(sorted_logs))  # lowest -> highest
        else:
            # Default: keep time order
            sorted_logs = t_logs

        per_train_sorted.append({"train": t, "logs": sorted_logs})

    # --- B) Train rankings by number of High / Low peaks (unchanged) ---
    train_stats = []
    for t in trains:
        t_logs = [log for log in logs if log.train.train_id == t.train_id]
        high_count = sum(1 for log in t_logs if log.capacity_level.lower() == "high")
        low_count = sum(1 for log in t_logs if log.capacity_level.lower() == "low")
        train_stats.append({
            "train": t,
            "high_count": high_count,
            "low_count": low_count,
        })

    trains_by_high = merge_sort(train_stats, lambda s: s["high_count"])
    trains_by_low = merge_sort(train_stats, lambda s: s["low_count"])

    context = {
        "target_date": target_date,
        "trains": trains,
        "rows": rows,                  # time-sorted grid
        "per_train_sorted": per_train_sorted,
        "trains_by_high": trains_by_high,
        "trains_by_low": trains_by_low,
        "sort_mode": sort_mode,        # <- used by the buttons
    }
    return render(request, "passenger_density/daily_report.html", context)

def daily_density_report_excel(request):
    date_str = request.GET.get("date")
    if date_str:
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    core = _build_daily_report_data(target_date)
    trains = core["trains"]
    rows = core["rows"]

    # Build a DataFrame: index = times, columns = Train N
    index = [row["label"] for row in rows]
    data = {}
    for col_idx, t in enumerate(trains):
        col_name = f"Train {t.train_id}"
        data[col_name] = [row["cells"][col_idx] for row in rows]

    df = pd.DataFrame(data, index=index)
    df.index.name = "Time"

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="DailyDensity")
    output.seek(0)

    filename = f"density_{target_date}.xlsx"
    resp = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

@require_POST
def snapshot_all_trains(request):
    """
    Take a snapshot of ALL trains' current capacity and density,
    logging one Historicalrecord per train (optionally only at last station).
    """
    last_station = Station.objects.order_by("order").last()
    now = timezone.now()

    # If you want ALL trains regardless of station, use Train.objects.all()
    trains = Train.objects.all()

    for t in trains:
        # If you want to restrict to last station only, uncomment:
        # if last_station and t.current_station != last_station:
        #     continue

        Historicalrecord.objects.create(
            train=t,
            station=t.current_station if t.current_station else last_station,
            timestamp=now,
            passenger_count=t.current_capacity,
            capacity_level=t.capacity_level,
        )

    return redirect("daily_density_report")
@require_POST
def clear_daily_report(request):
    """
    Delete all Historicalrecord rows for the selected date.
    Used to reset the daily report for that day.
    """
    import datetime

    date_str = request.POST.get("date")
    if date_str:
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    Historicalrecord.objects.filter(timestamp__date=target_date).delete()

    # Redirect back to the report page for that same date
    return redirect(f"{reverse('daily_density_report')}?date={target_date.isoformat()}")

def simulate_queue(request):
    if request.method == 'POST':
        station_name = request.POST.get('station')
        station = get_object_or_404(Station, name=station_name)

        # Initialize Queue
        train_queue = Queue()

        # Enqueue trains currently at the station
        trains_at_station = Train.objects.filter(current_station=station).order_by('last_updated')
        for train in trains_at_station:
            train_queue.push(train.train_id)

        # Dequeue trains to simulate processing
        processed_trains = []
        while not train_queue.is_empty():
            train_id = train_queue.pop()
            processed_trains.append(train_id)

        context = {
            'station': station,
            'processed_trains': processed_trains,
        }
        return render(request, 'passenger_density/simulation_result.html', context)
    else:
        return redirect('home')
# -- 2. Search Train (Linear Search) ---
def search_train(request):
    search_result = None
    search_message = None
    
    # 1. Fetch all trains (needed for the Dropdown AND the Search)
    all_trains = list(Train.objects.all())

    # 2. Check if the user picked something from the dropdown
    query = request.GET.get('train_id') 

    if query:
        # 3. Define the attribute function for linear search
        # We look for an exact match on the Train ID
        get_id_func = lambda t: str(t.train_id)

        # 4. Perform Linear Search using your custom function
        matches = linear_search(all_trains, query, get_id_func)

        if matches:
            found_train = matches[0]
            
            # Check if the train is currently assigned to a station
            if found_train.current_station:
                search_result = f"Train {found_train.train_id} ({found_train.name}) is currently at {found_train.current_station.name}."
            else:
                search_result = f"Train {found_train.train_id} ({found_train.name}) is currently in transit/inactive (not at any station)."
        else:
            # This handles the rare case where the ID in the dropdown 
            # might have been deleted from the DB between loading and clicking
            search_message = "Error: Selected train could not be found."

    context = {
        'trains': all_trains, # Pass the list to populate the dropdown
        'search_result': search_result,
        'search_message': search_message,
        'selected_train': query # To keep the dropdown selected on the current choice
    }
    return render(request, 'passenger_density/search_train.html', context)