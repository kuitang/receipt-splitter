"""
Django management command to generate test templates for JavaScript tests.
"""

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from pathlib import Path


class Command(BaseCommand):
    help = 'Generate test templates from Django'

    def handle(self, *args, **options):
        # Render templates
        html = render_to_string('receipts/partials/js_templates.html', {})
        
        # Write JS module
        js_path = Path('test/js/generated-templates.js')
        js_path.parent.mkdir(parents=True, exist_ok=True)
        escaped_html = html.replace('`', '\\`')
        js_path.write_text(f"""// Auto-generated - run: python manage.py generate_test_templates
export const testTemplates = `{escaped_html}`;
export function setupTestTemplates(document) {{
    const div = document.createElement('div');
    div.innerHTML = testTemplates;
    div.querySelectorAll('template').forEach(t => document.body.appendChild(t));
}}""")
        
        self.stdout.write(self.style.SUCCESS(f'Generated {js_path}'))