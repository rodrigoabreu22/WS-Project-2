"""Django management command: python manage.py run_spin_rules [--rule NAME]"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from championship.services.graphdb import GraphDBClient
from championship.spin_rules import SPIN_RULES, apply_all_rules, apply_rule


class Command(BaseCommand):
    help = "Apply SPIN inference rules to the GraphDB repository."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rule",
            metavar="NAME",
            help="Run only the named rule instead of all rules.",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List available rule names and exit.",
        )

    def handle(self, *args, **options):
        if options["list"]:
            self.stdout.write("Available SPIN rules:")
            for rule in SPIN_RULES:
                self.stdout.write(f"  {rule['name']} — {rule['description']}")
            return

        db = GraphDBClient()
        rule_name = options.get("rule")

        if rule_name:
            self.stdout.write(f"Running rule: {rule_name}")
            try:
                apply_rule(db, rule_name)
                self.stdout.write(self.style.SUCCESS(f"  OK: {rule_name}"))
            except ValueError as exc:
                self.stderr.write(self.style.ERROR(str(exc)))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  FAILED: {exc}"))
            return

        self.stdout.write(f"Applying {len(SPIN_RULES)} SPIN rules...")
        results = apply_all_rules(db)
        ok_count = sum(1 for r in results if r["ok"])
        for r in results:
            if r["ok"]:
                self.stdout.write(self.style.SUCCESS(f"  OK  {r['name']} ({r['elapsed']}s)"))
            else:
                self.stderr.write(self.style.ERROR(f"  ERR {r['name']}: {r['error']}"))
        self.stdout.write(f"\n{ok_count}/{len(SPIN_RULES)} rules applied successfully.")
