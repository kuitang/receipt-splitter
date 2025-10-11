from django import template
from fractions import Fraction

register = template.Library()

@register.filter
def format_fraction(value, denominator):
    if denominator == 1:
        return str(value)

    f = Fraction(value, denominator).limit_denominator()

    if f.denominator == 1:
        return str(f.numerator)

    # Basic unicode fractions
    unicode_fractions = {
        (1, 2): '½', (1, 3): '⅓', (2, 3): '⅔',
        (1, 4): '¼', (3, 4): '¾', (1, 5): '⅕',
        (2, 5): '⅖', (3, 5): '⅗', (4, 5): '⅘',
        (1, 6): '⅙', (5, 6): '⅚', (1, 8): '⅛',
        (3, 8): '⅜', (5, 8): '⅝', (7, 8): '⅞',
    }

    integer_part = f.numerator // f.denominator
    fractional_part = Fraction(f.numerator % f.denominator, f.denominator)

    display = ""
    if integer_part > 0:
        display += str(integer_part) + " "

    if (fractional_part.numerator, fractional_part.denominator) in unicode_fractions:
        display += unicode_fractions[(fractional_part.numerator, fractional_part.denominator)]
    else:
        display += f"{fractional_part.numerator}/{fractional_part.denominator}"

    return display.strip()
