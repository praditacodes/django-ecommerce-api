# Catalog overhaul: hierarchical categories, full product catalog, variants, images, reviews.

from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.core import validators as django_validators
from django.db.models import F, Q


def fill_product_skus(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for p in Product.objects.all().only('id', 'slug', 'sku'):
        base = (p.slug or str(p.pk)).upper()[:56]
        candidate = base
        suffix = 0
        while Product.objects.exclude(pk=p.pk).filter(sku=candidate).exists():
            suffix += 1
            candidate = f'{base}-{suffix}'
        Product.objects.filter(pk=p.pk).update(sku=candidate)


def noop_reverse(apps, schema_editor):  # pragma: no cover
    pass


def map_availability_forward(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(is_available=False).update(availability='out_of_stock')


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='children',
                to='products.category',
            ),
        ),
        migrations.AddField(
            model_name='category',
            name='meta_title',
            field=models.CharField(blank=True, max_length=70),
        ),
        migrations.AddField(
            model_name='category',
            name='meta_description',
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name='category',
            name='sort_order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='category',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ('sort_order', 'name')},
        ),
        migrations.RenameField(
            model_name='product',
            old_name='stock',
            new_name='stock_quantity',
        ),
        migrations.AddField(
            model_name='product',
            name='short_description',
            field=models.CharField(blank=True, max_length=320),
        ),
        migrations.AddField(
            model_name='product',
            name='brand',
            field=models.CharField(blank=True, db_index=True, max_length=128),
        ),
        migrations.AddField(
            model_name='product',
            name='discount_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='low_stock_threshold',
            field=models.PositiveIntegerField(
                default=5,
                help_text='Used for admin/listing alerts; not a DB constraint.',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='featured',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='product',
            name='availability',
            field=models.CharField(
                choices=[
                    ('available', 'Available'),
                    ('out_of_stock', 'Out of stock'),
                    ('preorder', 'Preorder'),
                ],
                db_index=True,
                default='available',
                max_length=20,
            ),
        ),
        migrations.RunPython(map_availability_forward, noop_reverse),
        migrations.RemoveField(model_name='product', name='is_available'),
        migrations.AddField(
            model_name='product',
            name='sku',
            field=models.CharField(db_index=True, max_length=64, null=True, unique=False),
        ),
        migrations.RunPython(fill_product_skus, noop_reverse),
        migrations.AlterField(
            model_name='product',
            name='sku',
            field=models.CharField(db_index=True, max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='name',
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='product',
            name='slug',
            field=models.SlugField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
        migrations.AlterField(
            model_name='product',
            name='category',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='products',
                to='products.category',
            ),
        ),
        migrations.AlterModelOptions(
            name='product',
            options={'ordering': ('-featured', '-created_at')},
        ),
        migrations.AddConstraint(
            model_name='product',
            constraint=models.CheckConstraint(
                condition=Q(stock_quantity__gte=0),
                name='product_stock_quantity_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='product',
            constraint=models.CheckConstraint(
                condition=Q(price__gte=Decimal('0.00')),
                name='product_price_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='product',
            constraint=models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(discount_price__gte=Decimal('0.00')),
                name='product_discount_price_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='product',
            constraint=models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(discount_price__lt=F('price')),
                name='product_discount_below_price',
            ),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=('category', 'availability'), name='products_pr_ca_avail_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(
                fields=('featured', '-created_at'),
                name='products_pr_feat_c_at_idx',
            ),
        ),
        migrations.CreateModel(
            name='ProductVariant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('size', models.CharField(max_length=64)),
                ('color', models.CharField(max_length=64)),
                (
                    'sku_suffix',
                    models.CharField(
                        blank=True,
                        help_text='Appended or combined with parent SKU during checkout/export.',
                        max_length=32,
                    ),
                ),
                ('stock_quantity', models.PositiveIntegerField(default=0)),
                (
                    'product',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='variants',
                        to='products.product',
                    ),
                ),
            ],
            options={
                'verbose_name_plural': 'Product variants',
                'constraints': [],
            },
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    'image',
                    models.ImageField(upload_to='catalog/products/%Y/%m/'),
                ),
                ('alt_text', models.CharField(blank=True, max_length=255)),
                ('is_primary', models.BooleanField(default=False)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                (
                    'product',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='images',
                        to='products.product',
                    ),
                ),
            ],
            options={'ordering': ('sort_order', 'id')},
        ),
        migrations.CreateModel(
            name='ProductReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    'rating',
                    models.PositiveSmallIntegerField(
                        validators=[
                            django_validators.MinValueValidator(1),
                            django_validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                ('comment', models.TextField()),
                (
                    'moderation_status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('approved', 'Approved'),
                            ('rejected', 'Rejected'),
                        ],
                        db_index=True,
                        default='pending',
                        max_length=16,
                    ),
                ),
                (
                    'verified_purchase',
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text='Set true automatically when wired to fulfilled orders.',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'product',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='reviews',
                        to='products.product',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='product_reviews',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.AddConstraint(
            model_name='productvariant',
            constraint=models.UniqueConstraint(
                fields=('product', 'size', 'color'),
                name='uniq_product_variant_size_color',
            ),
        ),
        migrations.AddConstraint(
            model_name='productvariant',
            constraint=models.CheckConstraint(
                condition=Q(stock_quantity__gte=0),
                name='variant_stock_non_negative',
            ),
        ),
        migrations.AddIndex(
            model_name='productvariant',
            index=models.Index(fields=('product', 'size'), name='products_pv_prod_sz_idx'),
        ),
        migrations.AddConstraint(
            model_name='productreview',
            constraint=models.UniqueConstraint(
                fields=('product', 'user'),
                name='one_review_per_user_product',
            ),
        ),
        migrations.AddIndex(
            model_name='productreview',
            index=models.Index(
                fields=('product', 'moderation_status'),
                name='products_prev_prod_mod_idx',
            ),
        ),
    ]
