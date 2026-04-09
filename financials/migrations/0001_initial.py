from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ticker', models.CharField(max_length=20, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('sector', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name_plural': 'companies', 'ordering': ['ticker']},
        ),
        migrations.CreateModel(
            name='Filing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period_label', models.CharField(max_length=50)),
                ('period_year', models.IntegerField()),
                ('period_quarter', models.IntegerField(default=0)),
                ('filing_date', models.CharField(blank=True, max_length=50)),
                ('pdf_file', models.FileField(blank=True, null=True, upload_to='pdfs/')),
                ('pdf_filename', models.CharField(blank=True, max_length=300)),
                ('status', models.CharField(choices=[('pending','Pending'),('processing','Processing'),('done','Done'),('failed','Failed')], default='pending', max_length=20)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('error_log', models.TextField(blank=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='filings', to='financials.company')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploads', to='accounts.user')),
            ],
            options={'ordering': ['-period_year', '-period_quarter']},
        ),
        migrations.CreateModel(
            name='Metric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=50)),
                ('label', models.CharField(max_length=100)),
                ('current_value', models.FloatField(blank=True, null=True)),
                ('prior_value', models.FloatField(blank=True, null=True)),
                ('filing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='metrics', to='financials.filing')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='filing',
            unique_together={('company', 'period_label')},
        ),
        migrations.AlterUniqueTogether(
            name='metric',
            unique_together={('filing', 'key')},
        ),
    ]
