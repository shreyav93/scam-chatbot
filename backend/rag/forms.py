from django import forms


class IngestionForm(forms.Form):
  title = forms.CharField(
      max_length=300,
      widget=forms.TextInput(
          attrs={"class": "form-control", "placeholder": "Document Title"}
      ),
  )
  publisher = forms.CharField(
      max_length=100,
      widget=forms.TextInput(
          attrs={
              "class": "form-control",
              "placeholder": "Publisher (e.g., FTC, Bank)",
          }
      ),
  )
  url = forms.URLField(
    required=False,
    widget=forms.URLInput(attrs={
        "class": "form-control",
        "placeholder": "Optional URL"
    })
    )
  category = forms.CharField(
      max_length=50,
      required=False,
      widget=forms.TextInput(
          attrs={
              "class": "form-control",
              "placeholder": "Category (e.g., impersonation)",
          }
      ),
  )
  channel = forms.CharField(
      max_length=30,
      required=False,
      widget=forms.TextInput(
          attrs={
              "class": "form-control",
              "placeholder": "Channel (text, phone, email)",
          }
      ),
  )
  file = forms.FileField(
      required=False,
      widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
  )
  raw_text = forms.CharField(
      required=False,
      widget=forms.Textarea(
          attrs={
              "class": "form-control",
              "placeholder": "Or paste raw text content here...",
              "rows": 5,
          }
      ),
  )

  def clean(self):
    cleaned = super().clean()
    has_file = bool(cleaned.get("file"))
    has_text = bool((cleaned.get("raw_text") or "").strip())
    if has_file == has_text:   # both or neither
      raise forms.ValidationError(
          "Provide either a file or pasted text, not both and not neither."
      )
    return cleaned