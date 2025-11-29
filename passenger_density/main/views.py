from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
import datetime
import numpy as np
import pandas as pd
from .models import Account, Station, train as Train, Historicalrecord
from .data import TrainNode, Queue, merge_sort, merge, linear_search

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
    return render(request, 'passenger_density/home.html')

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