from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('is_superuser', models.BooleanField(default=False)),
                ('email', models.EmailField(unique=True)),
                ('full_name', models.CharField(blank=True, max_length=150)),
                ('role', models.CharField(choices=[('superadmin','Super Admin'),('admin','Admin'),('viewer','Viewer')], default='viewer', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('is_staff', models.BooleanField(default=False)),
                ('date_joined', models.DateTimeField(auto_now_add=True)),
                ('last_login', models.DateTimeField(null=True, blank=True)),
                ('groups', models.ManyToManyField(blank=True, related_name='accounts_user_set', to='auth.group')),
                ('user_permissions', models.ManyToManyField(blank=True, related_name='accounts_user_set', to='auth.permission')),
            ],
            options={'abstract': False},
        ),
    ]
