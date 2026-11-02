from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Record",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("type", models.CharField(choices=[("income", "Income"), ("expense", "Expense")], db_index=True, max_length=16)),
                ("category", models.CharField(db_index=True, max_length=100)),
                ("date", models.DateField(db_index=True)),
                ("note", models.TextField(blank=True, default="")),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="records", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-date", "-created_at"],
                "indexes": [
                    models.Index(fields=["user", "date"], name="records_rec_user_id_date_6a72f5_idx"),
                    models.Index(fields=["category", "type"], name="records_rec_category_0ca5e6_idx"),
                    models.Index(fields=["is_deleted", "date"], name="records_rec_is_dele_25d7f8_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="record",
            constraint=models.CheckConstraint(check=models.Q(amount__gt=0), name="record_amount_positive"),
        ),
    ]
