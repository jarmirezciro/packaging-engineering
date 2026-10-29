from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..forms import UserPreferencesForm
from ..models import UserPreferences


@login_required
def user_settings(request):
    preferences = UserPreferences.objects.filter(user=request.user).first()
    if preferences is None:
        preferences = UserPreferences(user=request.user)
    if request.method == "POST":
        form = UserPreferencesForm(request.POST, instance=preferences)
        if form.is_valid():
            form.save()
            messages.success(request, "Units & Display preferences saved.")
            return redirect("user_settings")
    else:
        form = UserPreferencesForm(instance=preferences)

    return render(request, "account/user_settings.html", {"form": form})
