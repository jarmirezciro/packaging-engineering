"""Run the active suite against the public Transport engine."""
import sys

from capture_baselines import MODULES
from django.test.runner import DiscoverRunner

raise SystemExit(bool(DiscoverRunner(verbosity=1, interactive=False).run_tests(
    sys.argv[1:] or ["packagingapp.tests." + module for module in MODULES],
)))
