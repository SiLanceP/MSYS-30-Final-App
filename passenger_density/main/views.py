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
from .data import TrainNode, Queue, merge_sort, merge, linear_search, TrainHashTable
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
    
# --- 1. SIMULATION VIEW (Queue) ---
def home(request):
    # Stations ordered
    stations = Station.objects.order_by("order")

    station_rows = []
    for station in stations:
        queue = Train.objects.filter(current_station=station).order_by("last_updated")
        station_rows.append({
            "station": station,
            "queue": list(queue),
        })

    # All trains for dropdown
    all_trains = list(Train.objects.all().order_by("train_id"))

    # Hash Table to get all trains
    ht = TrainHashTable()
    ht.build_from_queryset(all_trains)
    hash_table_trains = list(ht.table.values())

    # Use linear_search to find the selected train
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
        "hash_table_trains": hash_table_trains,
    }
    return render(request, "passenger_density/home.html", context)

@require_POST
def advance_trains(request):
    stations = list(Station.objects.order_by("order"))
    if not stations:
        return redirect("home")

    now = timezone.now()
    # Process them in Westbound Order (Antipolo to Recto)
    for i in range(len(stations) - 1, -1, -1):
        station = stations[i]

        # 1) uses Queue and hash table for trains at this station
        trains_qs = Train.objects.filter(current_station=station).order_by("last_updated")
        if not trains_qs.exists():
            continue

        station_queue = Queue()
        table = TrainHashTable()
        table.build_from_queryset(trains_qs)  # train_id -> Train

        for t in trains_qs:
            station_queue.push(t.train_id)    # enqueue in First-in First-Out order

        if station_queue.is_empty():
            continue

        # 2) Pop the front of the queue (FIFO)
        front_id = station_queue.pop()
        front = table.get(front_id)          # hash table lookup
        if front is None:
            continue  

        # 3) Randomize passenger capacity once it passes a station
        front.current_capacity = random.randint(0, front.max_capacity)

        # 4) Move to next station or remove from line at the last station
        if i == len(stations) - 1:
            # Last station: train leaves the line (no next station)
            front.current_station = None
        else:
            next_station = stations[i + 1]
            front.current_station = next_station

        # 5) Update timestamp for queue ordering
        front.last_updated = now

        # 6) Save — your train.save() override will log this change
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
    id_lists = list({log.train.train_id for log in logs})
    #Merge sort the train IDs
    descending = merge_sort(id_lists, lambda x: x) # merge sort the train IDs
    train_ids = list(reversed(descending)) # mdae them ascending (1 - 5)
    trains = list(Train.objects.filter(train_id__in=train_ids).order_by("train_id"))

    # Time slots 4:00–22:00
    start_hour = 4
    end_hour = 22
    hours = list(range(start_hour, end_hour + 1))

    # grid[hour][train_id] = 'low' / 'medium' / 'high' / ''
    grid = {hour: {t.train_id: "" for t in trains} for hour in hours}

    for log in logs:
        local_ts = timezone.localtime(log.timestamp)
        hour = local_ts.hour
        if hour < start_hour or hour > end_hour:
            continue
        if log.train.train_id in grid[hour]:
            grid[hour][log.train.train_id] = log.capacity_level.lower()

    # Build rows for display
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
    # --- C1) Highest passenger capacity per train (max peaks, using linear_search) ---
    per_train_peaks = []
    for t in trains:
        t_logs = [log for log in logs if log.train.train_id == t.train_id]
        if not t_logs:
            continue

        max_capacity = max(log.passenger_count for log in t_logs)

        def attr_func(log):
            return str(log.passenger_count)

        max_logs = linear_search(t_logs, str(max_capacity), attr_func)
        max_logs.sort(key=lambda log: log.timestamp)

        per_train_peaks.append({
            "train": t,
            "max_capacity": max_capacity,
            "logs": max_logs,
        })

    # --- C2) Lowest passenger capacity per train (min peaks, using linear_search) ---
    per_train_min_peaks = []
    for t in trains:
        t_logs = [log for log in logs if log.train.train_id == t.train_id]
        if not t_logs:
            continue

        # exclude 0 if you want only real passenger counts;
        # change > 0 to >= 0 if you want to include zeros.
        non_empty_logs = [log for log in t_logs if log.passenger_count > 0]
        if not non_empty_logs:
            continue

        min_capacity = min(log.passenger_count for log in non_empty_logs)

        def min_attr_func(log):
            return str(log.passenger_count)

        min_logs = linear_search(non_empty_logs, str(min_capacity), min_attr_func)
        min_logs.sort(key=lambda log: log.timestamp)

        per_train_min_peaks.append({
            "train": t,
            "min_capacity": min_capacity,
            "logs": min_logs,
        })

    context["per_train_peaks"] = per_train_peaks
    context["per_train_min_peaks"] = per_train_min_peaks

    return render(request, "passenger_density/daily_report.html", context)

def daily_density_report_excel(request):
    # Same inputs as the HTML view
    date_str = request.GET.get("date")
    if date_str:
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    sort_mode = request.GET.get("sort", "time")  # only affects HTML view; here we export all modes

    core = _build_daily_report_data(target_date)
    logs = core["logs"]
    trains = core["trains"]
    rows = core["rows"]

    # ---------- 1) Time grid (what you see at the top of the page) ----------
    index = [row["label"] for row in rows]
    grid_data = {}
    for col_idx, t in enumerate(trains):
        col_name = f"Train {t.train_id}"
        grid_data[col_name] = [row["cells"][col_idx] for row in rows]
    df_grid = pd.DataFrame(grid_data, index=index)
    df_grid.index.name = "Time"

    # ---------- 2) Per-train events list (three variants) ----------
    events_time_rows = []
    events_high_rows = []
    events_low_rows = []

    for t in trains:
        t_logs = [log for log in logs if log.train.train_id == t.train_id]
        if not t_logs:
            continue

        # a) time order (as logged)
        for log in t_logs:
            events_time_rows.append({
                "Train": f"Train {t.train_id}",
                "Time": timezone.localtime(log.timestamp).strftime("%Y-%m-%d %I:%M %p"),
                "Station": log.station.name,
                "Passengers": log.passenger_count,
                "Density": log.capacity_level,
            })

        # b) sort High -> Low, then capacity (using merge_sort)
        def key_func(log):
            level = log.capacity_level.lower()
            score = DENSITY_SCORE.get(level, 0)
            return (score, log.passenger_count)

        high_sorted = merge_sort(t_logs, key_func)          # highest score first
        low_sorted = list(reversed(high_sorted))            # Lowest → Highest

        for log in high_sorted:
            events_high_rows.append({
                "Train": f"Train {t.train_id}",
                "Time": timezone.localtime(log.timestamp).strftime("%Y-%m-%d %I:%M %p"),
                "Station": log.station.name,
                "Passengers": log.passenger_count,
                "Density": log.capacity_level,
            })

        for log in low_sorted:
            events_low_rows.append({
                "Train": f"Train {t.train_id}",
                "Time": timezone.localtime(log.timestamp).strftime("%Y-%m-%d %I:%M %p"),
                "Station": log.station.name,
                "Passengers": log.passenger_count,
                "Density": log.capacity_level,
            })

    df_events_time = pd.DataFrame(events_time_rows)
    df_events_high = pd.DataFrame(events_high_rows)
    df_events_low = pd.DataFrame(events_low_rows)

    # ---------- 3) Rankings by High / Low peaks (separate sheets) ----------
    stats_rows = []
    for t in trains:
        t_logs = [log for log in logs if log.train.train_id == t.train_id]
        if not t_logs:
            continue
        high_count = sum(1 for log in t_logs if log.capacity_level.lower() == "high")
        low_count = sum(1 for log in t_logs if log.capacity_level.lower() == "low")
        stats_rows.append({
            "Train": f"Train {t.train_id}",
            "High peaks": high_count,
            "Low periods": low_count,
        })

    stats_by_high = merge_sort(stats_rows, lambda s: s["High peaks"])
    stats_by_low = merge_sort(stats_rows, lambda s: s["Low periods"])

    df_rank_high = pd.DataFrame(
        [{"Train": s["Train"], "High peaks": s["High peaks"]} for s in stats_by_high]
    )
    df_rank_low = pd.DataFrame(
        [{"Train": s["Train"], "Low periods": s["Low periods"]} for s in stats_by_low]
    )

    # ---------- 4) Peaks per train: Max and Min (using linear_search) ----------
    peaks_max_rows = []
    peaks_min_rows = []

    for t in trains:
        t_logs = [log for log in logs if log.train.train_id == t.train_id]
        if not t_logs:
            continue

        # Ignore completely empty logs for min/max if you want only real passenger counts.
        # If you want to include 0, remove this filter.
        non_empty_logs = [log for log in t_logs if log.passenger_count > 0]
        if not non_empty_logs:
            continue

        # Max capacity
        max_capacity = max(log.passenger_count for log in non_empty_logs)
        # Min capacity (lowest nonzero peak)
        min_capacity = min(log.passenger_count for log in non_empty_logs)

        def attr_func(log):
            return str(log.passenger_count)

        # Max peaks
        max_logs = linear_search(non_empty_logs, str(max_capacity), attr_func)
        max_logs.sort(key=lambda log: log.timestamp)

        max_times_str = "; ".join(
            f"{timezone.localtime(log.timestamp).strftime('%I:%M %p').lstrip('0')} "
            f"({log.station.name}, {log.capacity_level})"
            for log in max_logs
        )

        peaks_max_rows.append({
            "Train": f"Train {t.train_id}",
            "Max passengers": max_capacity,
            "Time(s)": max_times_str,
        })

        # Min peaks
        min_logs = linear_search(non_empty_logs, str(min_capacity), attr_func)
        min_logs.sort(key=lambda log: log.timestamp)

        min_times_str = "; ".join(
            f"{timezone.localtime(log.timestamp).strftime('%I:%M %p').lstrip('0')} "
            f"({log.station.name}, {log.capacity_level})"
            for log in min_logs
        )

        peaks_min_rows.append({
            "Train": f"Train {t.train_id}",
            "Min passengers": min_capacity,
            "Time(s)": min_times_str,
        })

    df_peaks_max = pd.DataFrame(peaks_max_rows)
    df_peaks_min = pd.DataFrame(peaks_min_rows)

    # ---------- Write all to a single Excel file ----------
    output = BytesIO()
    with pd.ExcelWriter(output) as writer:
        df_grid.to_excel(writer, sheet_name="Grid")

        if not df_events_time.empty:
            df_events_time.to_excel(writer, sheet_name="EventsTime", index=False)
        if not df_events_high.empty:
            df_events_high.to_excel(writer, sheet_name="EventsHighToLow", index=False)
        if not df_events_low.empty:
            df_events_low.to_excel(writer, sheet_name="EventsLowToHigh", index=False)

        if not df_rank_high.empty:
            df_rank_high.to_excel(writer, sheet_name="RankHigh", index=False)
        if not df_rank_low.empty:
            df_rank_low.to_excel(writer, sheet_name="RankLow", index=False)

        if not df_peaks_max.empty:
            df_peaks_max.to_excel(writer, sheet_name="PeaksMax", index=False)
        if not df_peaks_min.empty:
            df_peaks_min.to_excel(writer, sheet_name="PeaksMin", index=False)

    output.seek(0)

    filename = f"density_{target_date}.xlsx"
    resp = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename=\"{filename}\"'
    return resp

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

def search_train(request):
    search_result = None
    search_message = None

    # Build hash table of all trains
    all_trains_qs = Train.objects.all().order_by("train_id")
    all_trains = list(all_trains_qs)

    table = TrainHashTable()
    table.build_from_queryset(all_trains)

    query = request.GET.get("train_id")

    selected_train = None
    if query:
        try:
            q_id = int(query)
        except ValueError:
            q_id = None

        if q_id is not None:
            selected_train = table.get(q_id)  # O(1) hash table lookup

    if selected_train:
        if selected_train.current_station:
            search_result = (
                f"Train {selected_train.train_id} is currently at "
                f"{selected_train.current_station.name}."
            )
        else:
            search_result = (
                f"Train {selected_train.train_id} is currently in transit/inactive "
                f"(not at any station)."
            )
    elif query:
        search_message = "Train not found."

    context = {
        "trains": all_trains,
        "search_result": search_result,
        "search_message": search_message,
        "selected_train": query,
    }
    return render(request, "passenger_density/search_train.html", context)