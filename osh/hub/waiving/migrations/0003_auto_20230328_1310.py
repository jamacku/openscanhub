# Generated by Django 2.2.24 on 2023-03-28 13:10

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('waiving', '0002_auto_20211223_1124'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='result',
            name='scanner',
        ),
        migrations.RemoveField(
            model_name='result',
            name='scanner_version',
        ),
    ]
