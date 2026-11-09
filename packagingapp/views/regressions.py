from django.shortcuts import render

from ..tools.container.case_presets import CONTAINER_SELECTION_CASE_PRESETS
from ..tools.transport.case_presets import TRANSPORT_CONTAINER_CASE_PRESETS


def regressions(request):
    return render(
        request,
        "regressions.html",
        {
            "transport_cases": TRANSPORT_CONTAINER_CASE_PRESETS.items(),
            "container_cases": CONTAINER_SELECTION_CASE_PRESETS.items(),
        },
    )
