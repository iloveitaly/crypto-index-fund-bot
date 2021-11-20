# Generated by Django 3.2.6 on 2021-09-02 02:34

import encrypted_model_fields.fields
from django.db import migrations, models

import users.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("binance_api_key", encrypted_model_fields.fields.EncryptedCharField(null=True)),
                ("binance_secret_key", encrypted_model_fields.fields.EncryptedCharField(null=True)),
                ("external_portfolio", models.JSONField(decoder=users.models.CustomJSONDecoder, default=dict)),
                ("preferences", models.JSONField(default=dict)),
                ("name", models.CharField(max_length=100)),
                ("date_checked", models.DateTimeField(null=True)),
            ],
        ),
    ]
