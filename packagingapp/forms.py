from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from .models import CorrugatedBoardConstruction, PackagingCatalogue, PackagingMaterial
from .models import ProductCatalogue, Product
from .tools.product_shape import PRODUCT_SHAPE_CHOICES
from .tools.corrugated_material_strength.constants import (
    DISTRIBUTION_CHOICES,
    DISTRIBUTION_FACTORS,
    FLUTE_CHOICES,
    WALL_DOUBLE,
    WALL_SINGLE,
)


###
# Packaging Materials Section
###

class PackagingMaterialFilterForm(forms.Form):
    part_number = forms.CharField(required=False, label="Part Number")
    part_description = forms.CharField(required=False, label="Description")
    packaging_type = forms.CharField(required=False, label="Type")
    branding = forms.CharField(required=False, label="Brand")

    min_length = forms.DecimalField(required=False, label="Min Length")
    max_length = forms.DecimalField(required=False, label="Max Length")
    min_width = forms.DecimalField(required=False, label="Min Width")
    max_width = forms.DecimalField(required=False, label="Max Width")
    min_height = forms.DecimalField(required=False, label="Min Height")
    max_height = forms.DecimalField(required=False, label="Max Height")

    min_ext_length = forms.DecimalField(required=False, label="Min External Length")
    max_ext_length = forms.DecimalField(required=False, label="Max External Length")
    min_ext_width = forms.DecimalField(required=False, label="Min External Width")
    max_ext_width = forms.DecimalField(required=False, label="Max External Width")
    min_ext_height = forms.DecimalField(required=False, label="Min External Height")
    max_ext_height = forms.DecimalField(required=False, label="Max External Height")

    min_weight = forms.DecimalField(required=False, label="Min Weight")
    max_weight = forms.DecimalField(required=False, label="Max Weight")

    min_volume = forms.DecimalField(required=False, label="Min Volume")
    max_volume = forms.DecimalField(required=False, label="Max Volume")


class CatalogueAdministrationFormMixin:
    """Expose visibility/ownership fields only to catalogue administrators."""

    def __init__(self, *args, allow_public_management=False, **kwargs):
        super().__init__(*args, **kwargs)

        if not allow_public_management:
            self.fields.pop("is_public", None)
            self.fields.pop("owner", None)
            return

        is_public_field = self.fields.get("is_public")
        if is_public_field is not None:
            is_public_field.required = False
            is_public_field.label = "Public catalogue"
            is_public_field.help_text = "Enable this to make the catalogue visible to all users."
            is_public_field.widget.attrs.update({"class": "form-check-input"})

        owner_field = self.fields.get("owner")
        if owner_field is not None:
            owner_field.required = False
            owner_field.queryset = get_user_model().objects.order_by("username")
            owner_field.empty_label = "No owner / platform catalogue"
            owner_field.help_text = (
                "Leave blank for a platform public catalogue. "
                "Private catalogues without an owner will be assigned to you."
            )
            owner_field.widget.attrs.update({"class": "form-select"})


class PackagingCatalogueForm(CatalogueAdministrationFormMixin, forms.ModelForm):
    class Meta:
        model = PackagingCatalogue
        fields = ["name", "description", "picture", "is_public", "owner"]


class PackagingMaterialForm(forms.ModelForm):
    class Meta:
        model = PackagingMaterial
        fields = [
            "part_number",
            "part_description",
            "packaging_type",
            "branding",
            "packaging_materials",
            "part_length",
            "part_width",
            "part_height",
            "external_length",
            "external_width",
            "external_height",
            "part_weight",
            "drawing",
            "picture",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in [
            "part_number",
            "part_description",
            "packaging_materials",
            "part_length",
            "part_width",
            "part_height",
            "external_length",
            "external_width",
            "external_height",
            "part_weight",
        ]:
            self.fields[field_name].widget.attrs.update({"class": "form-control"})

        for field_name in ["packaging_type", "branding"]:
            self.fields[field_name].widget.attrs.update({"class": "form-select"})

        for field_name in [
            "part_length",
            "part_width",
            "part_height",
            "external_length",
            "external_width",
            "external_height",
            "part_weight",
        ]:
            self.fields[field_name].widget.attrs.update({"step": "any", "placeholder": "0"})

        self.fields["part_number"].widget.attrs.update({"placeholder": "e.g. BOX-001"})
        self.fields["part_description"].widget.attrs.update({"placeholder": "Short material description"})
        self.fields["packaging_materials"].widget.attrs.update({"placeholder": "e.g. Corrugated board, wood, plastic"})

        # Use a clean file input. Current files are shown by the template in modern preview cards.
        self.fields["drawing"].widget = forms.FileInput(attrs={"class": "form-control"})
        self.fields["picture"].widget = forms.FileInput(attrs={"class": "form-control", "accept": "image/*"})


class ExcelUploadForm(forms.Form):
    file = forms.FileField(label="Excel File (.xlsx)")


class DrawingUploadForm(forms.Form):
    zip_file = forms.FileField(label="ZIP File (.zip)")


class PackagingMaterialImagesZipUploadForm(forms.Form):
    zip_file = forms.FileField(
        label="ZIP File (.zip)",
        help_text="Upload a .zip containing packaging material pictures."
    )

###
# Container Selection Form
###

class ContainerSelectionMode1Form(forms.Form):
    MODE_CHOICES = [
        ("design", "Design Mode"),
        ("single", "Single container analysis"),
        ("optimal", "Optimal container (Top 5)"),
    ]

    PRODUCT_SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("catalogue", "From catalogue"),
    ]

    CONTAINER_SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("catalogue", "From catalogue"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial="single",
        required=True,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    product_source = forms.ChoiceField(
        choices=PRODUCT_SOURCE_CHOICES,
        initial="manual",
        required=True,
        widget=forms.RadioSelect
    )

    product_catalogue_id = forms.ChoiceField(
        required=False,
        label="Product Catalogue",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    selected_product_id = forms.CharField(required=False, widget=forms.HiddenInput())

    product_l = forms.FloatField(
        min_value=0.0001,
        label="Length",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    product_w = forms.FloatField(
        min_value=0.0001,
        label="Width",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    product_h = forms.FloatField(
        min_value=0.0001,
        label="Height",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    product_weight = forms.FloatField(
        min_value=0,
        required=False,
        label="Weight",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )

    desired_qty = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Units needed",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1"})
    )

    product_shape = forms.ChoiceField(
        choices=PRODUCT_SHAPE_CHOICES,
        initial="cuboid",
        required=False,
        label="Product shape",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    r1 = forms.BooleanField(required=False, initial=True, label="Allow rotation 1")
    r2 = forms.BooleanField(required=False, initial=True, label="Allow rotation 2")
    r3 = forms.BooleanField(required=False, initial=True, label="Allow rotation 3")

    container_source = forms.ChoiceField(
        choices=CONTAINER_SOURCE_CHOICES,
        initial="manual",
        widget=forms.RadioSelect,
        required=True,
    )

    catalogue_id = forms.ChoiceField(
        required=False,
        label="Packaging Catalogue",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    container_id = forms.CharField(required=False, widget=forms.HiddenInput())

    box_l = forms.FloatField(
        min_value=0.0001,
        required=False,
        label="Length",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    box_w = forms.FloatField(
        min_value=0.0001,
        required=False,
        label="Width",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    box_h = forms.FloatField(
        min_value=0.0001,
        required=False,
        label="Height",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )

    box_weight = forms.FloatField(
        min_value=0,
        required=False,
        label="Packaging weight",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any", "min": "0"})
    )

    box_max_payload = forms.FloatField(
        min_value=0,
        required=False,
        label="Max payload",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any", "min": "0"})
    )

    action = forms.CharField(required=False, widget=forms.HiddenInput())
    selected_design_candidate_id = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("mode") != "design":
            return cleaned
        if cleaned.get("desired_qty") is None:
            self.add_error("desired_qty", "Enter the desired quantity as a positive whole number.")
        if cleaned.get("product_source") == "manual":
            for field_name, label in (("product_l", "length"), ("product_w", "width"), ("product_h", "height")):
                if cleaned.get(field_name) is None:
                    self.add_error(field_name, f"Enter a product {label} greater than zero.")
        return cleaned

###
# Product Catalogue Section
###

class ProductFilterForm(forms.Form):
    product_id = forms.CharField(required=False, label="Product ID")
    product_name = forms.CharField(required=False, label="Product Name")

    min_length = forms.DecimalField(required=False, label="Min Length")
    max_length = forms.DecimalField(required=False, label="Max Length")
    min_width = forms.DecimalField(required=False, label="Min Width")
    max_width = forms.DecimalField(required=False, label="Max Width")
    min_height = forms.DecimalField(required=False, label="Min Height")
    max_height = forms.DecimalField(required=False, label="Max Height")

    min_weight = forms.DecimalField(required=False, label="Min Weight")
    max_weight = forms.DecimalField(required=False, label="Max Weight")

    min_desired_qty = forms.IntegerField(required=False, label="Min Desired Qty")
    max_desired_qty = forms.IntegerField(required=False, label="Max Desired Qty")

    min_volume = forms.DecimalField(required=False, label="Min Volume")
    max_volume = forms.DecimalField(required=False, label="Max Volume")


class ProductCatalogueForm(CatalogueAdministrationFormMixin, forms.ModelForm):
    class Meta:
        model = ProductCatalogue
        fields = ["name", "description", "picture", "is_public", "owner"]


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "product_id",
            "product_name",
            "product_length",
            "product_width",
            "product_height",
            "rotation_1",
            "rotation_2",
            "rotation_3",
            "weight",
            "desired_qty",
            "product_picture",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in [
            "product_id",
            "product_name",
            "product_length",
            "product_width",
            "product_height",
            "weight",
            "desired_qty",
        ]:
            self.fields[field_name].widget.attrs.update({"class": "form-control"})

        for field_name in ["product_length", "product_width", "product_height", "weight"]:
            self.fields[field_name].widget.attrs.update({"step": "any", "placeholder": "0"})

        self.fields["desired_qty"].widget.attrs.update({"min": "1", "placeholder": "1"})
        self.fields["product_id"].widget.attrs.update({"placeholder": "e.g. P-10001"})
        self.fields["product_name"].widget.attrs.update({"placeholder": "Short product name"})

        for field_name in ["rotation_1", "rotation_2", "rotation_3"]:
            self.fields[field_name].widget.attrs.update({"class": "catalogue-toggle-input"})

        # Use a clean file input. Current pictures are shown by the template in modern preview cards.
        self.fields["product_picture"].widget = forms.FileInput(attrs={"class": "form-control", "accept": "image/*"})


class ProductExcelUploadForm(forms.Form):
    file = forms.FileField(label="Excel File (.xlsx)")


class ProductImagesZipUploadForm(forms.Form):
    file = forms.FileField(help_text="Upload a .zip containing product images")


###
# Bag Selection Form
###


class BagSelectionForm(forms.Form):
    MODE_CHOICES = [
        ("design", "Design Mode"),
        ("single", "Single bag analysis"),
        ("optimal", "Optimal bag (Top 5)"),
    ]

    PRODUCT_SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("catalogue", "From catalogue"),
    ]

    BAG_SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("catalogue", "From catalogue"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial="single",
        required=True,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    product_source = forms.ChoiceField(
        choices=PRODUCT_SOURCE_CHOICES,
        initial="manual",
        required=True,
        widget=forms.RadioSelect
    )

    product_catalogue_id = forms.ChoiceField(
        required=False,
        label="Product Catalogue",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    selected_product_id = forms.CharField(required=False, widget=forms.HiddenInput())

    product_l = forms.FloatField(
        min_value=0.0001,
        label="Length",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    product_w = forms.FloatField(
        min_value=0.0001,
        label="Width",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    product_h = forms.FloatField(
        min_value=0.0001,
        label="Height",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )

    product_weight = forms.FloatField(
        min_value=0,
        label="Product weight (g)",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )

    desired_qty = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Target quantity",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1"})
    )

    product_shape = forms.ChoiceField(
        choices=PRODUCT_SHAPE_CHOICES,
        initial="cuboid",
        required=False,
        label="Product shape",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    bag_source = forms.ChoiceField(
        choices=BAG_SOURCE_CHOICES,
        initial="manual",
        widget=forms.RadioSelect,
        required=True,
    )

    catalogue_id = forms.ChoiceField(
        required=False,
        label="Packaging Catalogue",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    bag_id = forms.CharField(required=False, widget=forms.HiddenInput())

    bag_length = forms.FloatField(
        min_value=0.0001,
        required=False,
        label="Bag length",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    bag_width = forms.FloatField(
        min_value=0.0001,
        required=False,
        label="Bag width",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )

    bag_weight = forms.FloatField(
        min_value=0,
        required=False,
        label="Packaging weight (g)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )

    bag_max_payload = forms.FloatField(
        min_value=0,
        required=False,
        label="Max payload (g)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )

    action = forms.CharField(required=False, widget=forms.HiddenInput())
    selected_design_candidate_id = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("mode") != "design":
            return cleaned
        if cleaned.get("desired_qty") is None:
            self.add_error("desired_qty", "Enter the desired quantity as a positive whole number.")
        if cleaned.get("product_source") == "manual":
            for field_name, label in (("product_l", "length"), ("product_w", "width"), ("product_h", "height")):
                if cleaned.get(field_name) is None:
                    self.add_error(field_name, f"Enter a product {label} greater than zero.")
        return cleaned


class PalletizationForm(forms.Form):
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("catalogue", "From Catalogue"),
    ]

    action = forms.CharField(required=False, widget=forms.HiddenInput())

    # BOX / LOAD
    box_source = forms.ChoiceField(
        choices=SOURCE_CHOICES,
        initial="manual",
        widget=forms.RadioSelect
    )
    box_catalogue_id = forms.ChoiceField(
        required=False,
        choices=[("", "— Select —")],
        widget=forms.Select(attrs={"class": "form-select"})
    )
    selected_box_id = forms.CharField(required=False, widget=forms.HiddenInput())

    box_l = forms.FloatField(required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    box_w = forms.FloatField(required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    box_h = forms.FloatField(required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    box_weight = forms.FloatField(required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    max_weight_on_bottom_box = forms.FloatField(required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))

    # PALLET
    pallet_source = forms.ChoiceField(
        choices=SOURCE_CHOICES,
        initial="manual",
        widget=forms.RadioSelect
    )
    pallet_catalogue_id = forms.ChoiceField(
        required=False,
        choices=[("", "— Select —")],
        widget=forms.Select(attrs={"class": "form-select"})
    )
    pallet_id = forms.CharField(required=False, widget=forms.HiddenInput())

    pallet_l = forms.FloatField(required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    pallet_w = forms.FloatField(required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    pallet_height = forms.FloatField(required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))

    # CONSTRAINTS
    max_stack_height = forms.FloatField(required=False, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    max_width_stickout = forms.FloatField(required=False, initial=0, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    max_length_stickout = forms.FloatField(required=False, initial=0, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action") or ""

        # allow refresh actions without forcing validation
        if action not in ("run_analysis", "select_result"):
            return cleaned

        box_source = cleaned.get("box_source") or "manual"
        pallet_source = cleaned.get("pallet_source") or "manual"

        if box_source == "manual":
            if cleaned.get("box_l") is None or cleaned.get("box_w") is None or cleaned.get("box_h") is None:
                raise forms.ValidationError("Please enter all manual box dimensions.")
        else:
            if not cleaned.get("selected_box_id"):
                raise forms.ValidationError("Please select a box/container from the catalogue table.")

        if pallet_source == "manual":
            if cleaned.get("pallet_l") is None or cleaned.get("pallet_w") is None:
                raise forms.ValidationError("Please enter pallet length and pallet width.")
        else:
            if not cleaned.get("pallet_id"):
                raise forms.ValidationError("Please select a pallet from the catalogue table.")

        if cleaned.get("max_stack_height") is None:
            raise forms.ValidationError("Please enter max stack height.")

        positive_fields = ["box_l", "box_w", "box_h", "pallet_l", "pallet_w", "pallet_height", "max_stack_height"]
        for fld in positive_fields:
            value = cleaned.get(fld)
            if value is not None and value <= 0:
                self.add_error(fld, "Value must be greater than 0.")

        non_negative_fields = ["box_weight", "max_weight_on_bottom_box", "max_width_stickout", "max_length_stickout"]
        for fld in non_negative_fields:
            value = cleaned.get(fld)
            if value is not None and value < 0:
                self.add_error(fld, "Value cannot be negative.")

        return cleaned


class ContainerToolForm(forms.Form):
    CONTAINER_SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("catalogue", "From catalogue"),
    ]
    PACKING_MODE_CHOICES = [
        ("maximum_utilization", "Maximum utilization"),
        ("accessible_sequence_loading", "Sequence loading"),
        # Keep the legacy engine value for backward compatibility. Its
        # user-facing name is now Strict sequence loading.
        ("sequence_loading", "Strict sequence loading"),
    ]

    action = forms.CharField(required=False, widget=forms.HiddenInput())

    packing_mode = forms.ChoiceField(
        choices=PACKING_MODE_CHOICES,
        initial="maximum_utilization",
        required=True,
        widget=forms.RadioSelect,
        label="Packing mode",
    )

    container_source = forms.ChoiceField(
        choices=CONTAINER_SOURCE_CHOICES,
        initial="manual",
        required=True,
        widget=forms.RadioSelect
    )

    catalogue_id = forms.ChoiceField(
        required=False,
        label="Packaging Catalogue",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    container_id = forms.CharField(required=False, widget=forms.HiddenInput())

    container_l = forms.FloatField(
        min_value=0.0001,
        label="Internal length (mm)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    container_w = forms.FloatField(
        min_value=0.0001,
        label="Internal width (mm)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    container_h = forms.FloatField(
        min_value=0.0001,
        label="Internal height (mm)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    max_weight = forms.FloatField(
        required=False,
        min_value=0.0,
        label="Max payload (kg)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    tare_weight = forms.FloatField(
        required=False,
        min_value=0.0,
        label="Tare weight (kg)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )


class ContactForm(forms.Form):
    AREA_CHOICES = [
        ("KolliPack app", "KolliPack app"),
        ("Packaging consultancy", "Packaging consultancy"),
        ("Packaging project management", "Packaging project management"),
        ("Packaging optimization", "Packaging optimization"),
        ("Packaging education / training", "Packaging education / training"),
        ("Other", "Other"),
    ]

    name = forms.CharField(
        max_length=120,
        label="Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Your name"}),
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@example.com"}),
    )
    company = forms.CharField(
        max_length=160,
        required=False,
        label="Company",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Company name"}),
    )
    area_of_interest = forms.ChoiceField(
        choices=AREA_CHOICES,
        label="Area of interest",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Tell us briefly what you would like to evaluate, optimize, or discuss.",
            }
        ),
    )
    consent = forms.BooleanField(
        label="I agree to be contacted by KolliLabs about my request.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "d-none", "tabindex": "-1", "autocomplete": "off"}),
    )

    def clean_website(self):
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("Invalid submission.")
        return value


class CorrugatedMaterialStrengthForm(forms.Form):
    """Standalone input form; catalogue/manual values are never persisted."""

    action = forms.CharField(required=False, widget=forms.HiddenInput())
    box_length_mm = forms.DecimalField(label="Internal length (mm)", min_value=Decimal("0.0001"), initial=400, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    box_width_mm = forms.DecimalField(label="Internal width (mm)", min_value=Decimal("0.0001"), initial=300, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    box_height_mm = forms.DecimalField(label="Internal height (mm)", min_value=Decimal("0.0001"), initial=200, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    product_weight_g = forms.DecimalField(label="Product net weight (g)", min_value=Decimal("0"), initial=200, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    quantity = forms.IntegerField(label="Production quantity", min_value=1, initial=1000, widget=forms.NumberInput(attrs={"class": "form-control", "step": "1"}))
    fefco_code = forms.ChoiceField(label="Box style", choices=(("0201", "FEFCO 0201 — regular slotted case"),), initial="0201", widget=forms.Select(attrs={"class": "form-select"}))
    joint_width_mm = forms.DecimalField(label="Manufacturer’s joint (mm)", min_value=Decimal("0"), initial=40, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    sheet_margin_per_edge_mm = forms.DecimalField(label="Production-sheet margin per edge (mm)", min_value=Decimal("0"), initial=20, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))

    pallet_source = forms.ChoiceField(label="Pallet source", choices=(("manual", "Manual"), ("catalogue", "Existing pallet catalogue")), initial="manual", widget=forms.RadioSelect)
    pallet_code = forms.ChoiceField(label="Pallet type", required=False, choices=(("", "— Select existing pallet —"),), widget=forms.Select(attrs={"class": "form-select"}))
    pallet_length_mm = forms.DecimalField(label="Pallet length (mm)", min_value=Decimal("0.0001"), initial=1200, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    pallet_width_mm = forms.DecimalField(label="Pallet width (mm)", min_value=Decimal("0.0001"), initial=800, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    pallet_height_mm = forms.DecimalField(label="Pallet height (mm)", min_value=Decimal("0"), initial=144, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    pallet_weight_kg = forms.DecimalField(label="Pallet weight (kg)", min_value=Decimal("0"), initial=0, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    max_palletized_height_mm = forms.DecimalField(label="Maximum palletized height including pallet (mm)", min_value=Decimal("0"), initial=1200, widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    pattern = forms.ChoiceField(label="Layer pattern", choices=(("COLUMN_ALIGNED", "Column aligned"), ("INTERLOCKED", "Interlocked (same load model)")), initial="COLUMN_ALIGNED", widget=forms.Select(attrs={"class": "form-select"}))
    stacked_pallets = forms.IntegerField(label="Vertically stacked pallets", min_value=1, initial=1, widget=forms.NumberInput(attrs={"class": "form-control", "step": "1"}))

    board_mode = forms.ChoiceField(label="Board source", choices=(("catalogue", "Select from catalogue"), ("manual", "Manual one-time entry")), initial="catalogue", widget=forms.RadioSelect)
    board_construction_id = forms.ChoiceField(label="Corrugated construction", required=False, choices=(("", "— Select construction —"),), widget=forms.Select(attrs={"class": "form-select"}))
    manual_wall_type = forms.ChoiceField(label="Wall type", required=False, choices=((WALL_SINGLE, "Single wall"), (WALL_DOUBLE, "Double wall")), initial=WALL_SINGLE, widget=forms.Select(attrs={"class": "form-select"}))
    manual_flute_1 = forms.ChoiceField(label="Flute 1", required=False, choices=(("", "— Select flute —"),) + tuple(FLUTE_CHOICES), widget=forms.Select(attrs={"class": "form-select"}))
    manual_flute_2 = forms.ChoiceField(label="Flute 2", required=False, choices=(("", "— Select flute —"),) + tuple(FLUTE_CHOICES), widget=forms.Select(attrs={"class": "form-select"}))
    manual_combined_grammage_g_m2 = forms.DecimalField(label="Combined grammage (g/m²)", required=False, min_value=Decimal("0.0001"), widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    ect_override_kn_m = forms.DecimalField(label="ECT override (kN/m)", required=False, min_value=Decimal("0.0001"), widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    caliper_override_mm = forms.DecimalField(label="Actual caliper override (mm)", required=False, min_value=Decimal("0.0001"), widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    measured_bct_override_n = forms.DecimalField(label="Measured BCT override (N)", required=False, min_value=Decimal("0.0001"), widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))

    distribution_profile = forms.ChoiceField(label="Distribution profile", choices=DISTRIBUTION_CHOICES, initial="NORMAL", widget=forms.Select(attrs={"class": "form-select"}))
    distribution_factor = forms.DecimalField(label="Distribution factor", required=False, initial=DISTRIBUTION_FACTORS["NORMAL"], min_value=Decimal("0.0001"), widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))

    co2_mode = forms.ChoiceField(label="CO₂ factor", choices=(("CONSTRUCTION", "Use construction factor"), ("CUSTOM", "Use custom factor")), initial="CONSTRUCTION", widget=forms.RadioSelect)
    custom_co2_factor_kg_per_kg = forms.DecimalField(label="Custom kg CO₂e/kg", required=False, min_value=Decimal("0"), widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}))
    custom_co2_source = forms.CharField(label="Custom CO₂ source label", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    custom_co2_boundary = forms.CharField(label="Custom CO₂ boundary", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))

    reference_ect_grade_id = forms.ChoiceField(
        label="Reference ECT category",
        required=False,
        choices=(("", "\u2014 Select reference ECT category \u2014"),),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, reference_grades=None, board_constructions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reference_grades = {
            str(getattr(item, "pk", getattr(item, "id", ""))): item
            for item in (reference_grades or [])
        }
        if reference_grades is not None:
            self.fields["reference_ect_grade_id"].choices = [
                ("", "\u2014 Select reference ECT category \u2014"),
                *[(str(item.pk), self._reference_grade_label(item)) for item in reference_grades],
            ]
        self.board_constructions = {
            str(getattr(item, "pk", getattr(item, "id", ""))): item
            for item in (board_constructions or [])
        }

    @staticmethod
    def _reference_grade_label(grade):
        caliper = getattr(grade, "reference_caliper_mm", None)
        caliper_text = f"reference caliper {caliper:g} mm"
        wall_text = "double wall" if grade.wall_type == WALL_DOUBLE else "flute"
        return f"{grade.flute_family} {wall_text} - {grade.ect_lb_in:g} ECT - {grade.ect_kn_m:.3f} kN/m - {caliper_text}"

    def _selected_flute_family(self, cleaned):
        if cleaned.get("board_mode") == "catalogue":
            construction = self.board_constructions.get(str(cleaned.get("board_construction_id")))
            if construction is not None:
                return construction.wall_type, construction.flute_display
            return None, None
        wall_type = cleaned.get("manual_wall_type")
        flute_1 = cleaned.get("manual_flute_1") or ""
        flute_2 = cleaned.get("manual_flute_2") or ""
        return wall_type, f"{flute_1}{flute_2}" if wall_type == WALL_DOUBLE else flute_1

    def _validate_reference_grade_compatibility(self, cleaned):
        grade_id = cleaned.get("reference_ect_grade_id")
        if not grade_id or not self.reference_grades:
            return
        grade = self.reference_grades.get(str(grade_id))
        if grade is None or not getattr(grade, "is_active", True):
            self.add_error("reference_ect_grade_id", "Select an active reference ECT category.")
            return
        wall_type, flute_family = self._selected_flute_family(cleaned)
        if wall_type and flute_family and (grade.wall_type != wall_type or grade.flute_family != flute_family):
            self.add_error("reference_ect_grade_id", "The selected reference ECT category does not match the selected flute family.")

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action") or "run_analysis"
        if action not in ("", "run_analysis", "export_pdf"):
            return cleaned

        if cleaned.get("pallet_source") == "catalogue" and not cleaned.get("pallet_code"):
            self.add_error("pallet_code", "Select a pallet from the existing catalogue.")
        if cleaned.get("board_mode") == "catalogue" and not cleaned.get("board_construction_id"):
            self.add_error("board_construction_id", "Select a corrugated construction from the catalogue.")
        if cleaned.get("board_mode") == "manual":
            if not cleaned.get("manual_combined_grammage_g_m2"):
                self.add_error("manual_combined_grammage_g_m2", "Enter a combined grammage for the manual board entry.")
            if not cleaned.get("manual_flute_1"):
                self.add_error("manual_flute_1", "Select flute 1.")
            if cleaned.get("manual_wall_type") == WALL_DOUBLE and not cleaned.get("manual_flute_2"):
                self.add_error("manual_flute_2", "Select flute 2 for a double-wall entry.")

        self._validate_reference_grade_compatibility(cleaned)

        ect = cleaned.get("ect_override_kn_m")
        caliper = cleaned.get("caliper_override_mm")
        if (ect is None) != (caliper is None):
            self.add_error(None, "Enter both ECT and actual finished-board caliper to calculate McKee BCT.")

        if cleaned.get("distribution_profile") == "CUSTOM" and cleaned.get("distribution_factor") is None:
            self.add_error("distribution_factor", "Enter a custom distribution factor greater than zero.")
        if cleaned.get("co2_mode") == "CUSTOM":
            if cleaned.get("custom_co2_factor_kg_per_kg") is None:
                self.add_error("custom_co2_factor_kg_per_kg", "Enter a custom CO₂ factor or use the construction factor.")
            if not cleaned.get("custom_co2_source"):
                self.add_error("custom_co2_source", "Enter the custom CO₂ source label.")
            if not cleaned.get("custom_co2_boundary"):
                self.add_error("custom_co2_boundary", "Enter the custom CO₂ boundary.")

        pallet_height = cleaned.get("pallet_height_mm")
        max_height = cleaned.get("max_palletized_height_mm")
        if pallet_height is not None and max_height is not None and max_height <= pallet_height:
            self.add_error("max_palletized_height_mm", "The maximum palletized height must exceed pallet height.")

        return cleaned
