from django.shortcuts import render

from ..tools.bag.case_presets import BAG_SELECTION_CASE_PRESETS
from ..tools.container.case_presets import CONTAINER_SELECTION_CASE_PRESETS
from ..tools.full_packaging.case_presets import get_case_titles
from ..tools.palletization.case_presets import PALLETIZATION_CASE_PRESETS
from ..tools.transport.case_presets import TRANSPORT_CONTAINER_CASE_PRESETS


def regressions(request):
    return render(
        request,
        "regressions.html",
        {
            "transport_cases": TRANSPORT_CONTAINER_CASE_PRESETS.items(),
            "container_cases": CONTAINER_SELECTION_CASE_PRESETS.items(),
            "palletization_cases": PALLETIZATION_CASE_PRESETS.items(),
            "bag_cases": BAG_SELECTION_CASE_PRESETS.items(),
            "flow_cases": get_case_titles(),
        },
    )
