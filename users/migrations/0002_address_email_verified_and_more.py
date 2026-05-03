# Generated migration for signup verification tracking + Address model.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def mark_existing_active_accounts_verified(apps, schema_editor):
    UserModel = apps.get_model('users', 'User')
    UserModel.objects.filter(is_active=True).update(email_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='True after clicking the signup verification link.',
            ),
        ),
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('label', models.CharField(blank=True, max_length=80)),
                ('recipient_name', models.CharField(max_length=255)),
                ('phone', models.CharField(max_length=20)),
                ('address_line_1', models.CharField(max_length=255)),
                ('address_line_2', models.CharField(blank=True, max_length=255)),
                ('city', models.CharField(max_length=120)),
                ('state_province', models.CharField(blank=True, max_length=120)),
                ('postal_code', models.CharField(max_length=32)),
                ('country', models.CharField(max_length=2)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='addresses',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name_plural': 'Addresses',
                'indexes': [
                    models.Index(
                        fields=['user', '-created_at'],
                        name='users_adrs_user_crt_dt',
                    ),
                ],
            },
        ),
        migrations.RunPython(
            mark_existing_active_accounts_verified,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
