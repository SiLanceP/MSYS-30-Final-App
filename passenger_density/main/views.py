from django.shortcuts import render
from django.http import HttpResponse
import time
import datetime
import numpy as np
import pandas as pd
from django.utils import timezone
from .models import Account, Station, train, Historicalrecord
from .data import TrainNode, Queue, merge_sort, merge, linear_search

# Create your views here.

def home(request):
    context = {
        'time': datetime.datetime.now() # Add the time
    }
    return render(request, 'passenger_density/home.html', context)