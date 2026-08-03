"""Corrugated Material & Strength domain package.

The calculation modules in this package are deliberately independent from
Django views and templates.  They are suitable for the future Packaging Flow
consumer as well as the standalone tool.
"""

from .service import calculate_corrugated_material_strength

__all__ = ["calculate_corrugated_material_strength"]
