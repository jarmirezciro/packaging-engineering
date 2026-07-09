from django import forms
from django.contrib.auth import get_user_model

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
