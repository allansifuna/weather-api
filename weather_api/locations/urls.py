from django.urls import path

from .views import LocationTemperatureStatsView

urlpatterns = [
    path("<str:city>/", LocationTemperatureStatsView.as_view(), name="location-temperature-stats"),
]
