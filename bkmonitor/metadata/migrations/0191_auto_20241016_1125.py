# Generated by Django 3.2.15 on 2024-10-16 03:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('metadata', '0190_merge_20240918_1322'),
    ]

    operations = [
        migrations.AddField(
            model_name='accessvmrecord',
            name='bk_base_data_name',
            field=models.CharField(default='', help_text='计算平台数据名称', max_length=64, verbose_name='计算平台数据名称'),
        ),
        migrations.AlterField(
            model_name='accessvmrecord',
            name='bk_base_data_id',
            field=models.IntegerField(help_text='计算平台数据ID', verbose_name='计算平台数据ID'),
        ),
    ]
