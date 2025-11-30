"""
URL configuration for passenger_density project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", views.home, name="home"),
    path("advance/", views.advance_trains, name="advance_trains"),
    path("reset/", views.reset_trains_to_start, name="reset_trains_to_start"),
    path("train/<int:train_id>/capacity/", views.update_capacity, name="update_capacity"),
    path("report/daily/", views.daily_density_report, name="daily_density_report"),
    path("report/daily/excel/", views.daily_density_report_excel, name="daily_density_report_excel"),
    path("report/daily/clear/", views.clear_daily_report, name="clear_daily_report"),
    path("snapshot/", views.snapshot_all_trains, name="snapshot_all_trains"),
]
