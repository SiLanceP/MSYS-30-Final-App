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
def home(request):
    return render(request, 'passenger_density/home.html')