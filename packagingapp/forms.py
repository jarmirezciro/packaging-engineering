from django import forms
from .models import PackagingCatalogue, PackagingMaterial
from .models import ProductCatalogue, Product


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


class PackagingCatalogueForm(forms.ModelForm):
    class Meta:
        model = PackagingCatalogue
        fields = ["name", "description", "picture"]


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
        ]


class ExcelUploadForm(forms.Form):
    file = forms.FileField(label="Excel File (.xlsx)")


class DrawingUploadForm(forms.Form):
    zip_file = forms.FileField(label="ZIP File (.zip)")

###
# Container Selection Form
###

class ContainerSelectionMode1Form(forms.Form):
    MODE_CHOICES = [
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

    action = forms.CharField(required=False, widget=forms.HiddenInput())

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


class ProductCatalogueForm(forms.ModelForm):
    class Meta:
        model = ProductCatalogue
        fields = ["name", "description", "picture"]


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


class ProductExcelUploadForm(forms.Form):
    file = forms.FileField(label="Excel File (.xlsx)")


class ProductImagesZipUploadForm(forms.Form):
    file = forms.FileField(help_text="Upload a .zip containing product images")


###
# Bag Selection Form
###


class BagSelectionForm(forms.Form):
    MODE_CHOICES = [
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

    desired_qty = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Units needed",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1"})
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

    action = forms.CharField(required=False, widget=forms.HiddenInput())


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

        positive_fields = ["box_l", "box_w", "box_h", "pallet_l", "pallet_w", "max_stack_height"]
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

    action = forms.CharField(required=False, widget=forms.HiddenInput())

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
        label="Internal length",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    container_w = forms.FloatField(
        min_value=0.0001,
        label="Internal width",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    container_h = forms.FloatField(
        min_value=0.0001,
        label="Internal height",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )
    max_weight = forms.FloatField(
        min_value=0.0,
        label="Max weight",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"})
    )