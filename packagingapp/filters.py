import django_filters
from .models import PackagingMaterial

class PackagingMaterialFilter(django_filters.FilterSet):
    part_number = django_filters.CharFilter(lookup_expr='icontains', label='Part Number')
    part_description = django_filters.CharFilter(lookup_expr='icontains', label='Description')
    packaging_type = django_filters.ChoiceFilter(choices=PackagingMaterial.PACKAGING_TYPES)
    branding = django_filters.ChoiceFilter(choices=PackagingMaterial.BRANDS)
    part_length__gte = django_filters.NumberFilter(field_name='part_length', lookup_expr='gte', label='Min Length')
    part_length__lte = django_filters.NumberFilter(field_name='part_length', lookup_expr='lte', label='Max Length')
    part_width__gte = django_filters.NumberFilter(field_name='part_width', lookup_expr='gte', label='Min Width')
    part_width__lte = django_filters.NumberFilter(field_name='part_width', lookup_expr='lte', label='Max Width')
    part_height__gte = django_filters.NumberFilter(field_name='part_height', lookup_expr='gte', label='Min Height')
    part_height__lte = django_filters.NumberFilter(field_name='part_height', lookup_expr='lte', label='Max Height')
    part_volume__gte = django_filters.NumberFilter(field_name='part_volume', lookup_expr='gte', label='Min Volume')
    part_volume__lte = django_filters.NumberFilter(field_name='part_volume', lookup_expr='lte', label='Max Volume')

    class Meta:
        model = PackagingMaterial
        fields = []
