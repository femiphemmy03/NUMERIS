from django.db import models
from django.conf import settings


class Company(models.Model):
    ticker      = models.CharField(max_length=20, unique=True)
    name        = models.CharField(max_length=200)
    sector      = models.CharField(max_length=100, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'companies'
        ordering = ['ticker']

    def __str__(self):
        return f"{self.ticker} — {self.name}"


class Filing(models.Model):
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('done',       'Done'),
        ('failed',     'Failed'),
    ]

    company      = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='filings')
    period_label = models.CharField(max_length=50)   # e.g. "Q3 2025"
    period_year  = models.IntegerField()
    period_quarter = models.IntegerField(default=0)  # 0=annual, 1-4=quarterly
    filing_date  = models.CharField(max_length=50, blank=True)
    pdf_file     = models.FileField(upload_to='pdfs/', null=True, blank=True)
    pdf_filename = models.CharField(max_length=300, blank=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    uploaded_by  = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='uploads')
    uploaded_at  = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_log    = models.TextField(blank=True)

    class Meta:
        ordering = ['-period_year', '-period_quarter']
        unique_together = ['company', 'period_label']

    def __str__(self):
        return f"{self.company.ticker} {self.period_label}"


class Metric(models.Model):
    filing       = models.ForeignKey(Filing, on_delete=models.CASCADE, related_name='metrics')
    key          = models.CharField(max_length=50)   # e.g. 'revenue', 'pat'
    label        = models.CharField(max_length=100)  # e.g. 'Revenue'
    current_value = models.FloatField(null=True, blank=True)
    prior_value  = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ['filing', 'key']

    def __str__(self):
        return f"{self.filing} | {self.key} = {self.current_value}"
