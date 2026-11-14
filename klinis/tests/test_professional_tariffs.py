from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase


class ProfessionalPriceTest(SimpleTestCase):
    def test_currency_rounds_per_line_half_up(self):
        from klinis.services.professional_tariffs import price_breakdown
        self.assertEqual(price_breakdown('0.67','0','1.5')['subtotal'],Decimal('1.01'))
    def test_component_sum(self):
        from klinis.services.professional_tariffs import price_breakdown
        result = price_breakdown('50000', '150000', '2')
        self.assertEqual(result['unit_total'], Decimal('200000.00'))
        self.assertEqual(result['subtotal'], Decimal('400000.00'))

    def test_invalid_money_or_quantity(self):
        from klinis.services.professional_tariffs import price_breakdown
        for values in [('-1','1','1'), ('NaN','1','1'), ('Infinity','1','1'), ('0','1','0'), ('0','1','1.001'), ('0','0.001','1'), ('9999999999.99','1','1'), ('0','1','1000000')]:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                price_breakdown(*values)

    def test_free_arithmetic_is_not_an_approval(self):
        from klinis.services.professional_tariffs import price_breakdown
        self.assertEqual(price_breakdown('0', '0', '1')['subtotal'], Decimal('0'))
