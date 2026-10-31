#!/usr/bin/env python3
"""Validate this planning pack and its numerical examples, not the application."""
from __future__ import annotations

import calendar
import json
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENT = Decimal('0.01')
ZERO = Decimal('0.00')

def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def calculate(case: dict) -> dict:
    lines = list(case['lines'])
    base = Decimal(case['base_fee'])
    if base:
        lines = [{'key': 'BASE', 'price': str(base), 'variant_delta': '0.00',
                  'quantity': 1, 'tax_rates': case['base_tax_rates']}] + lines
    gross = [money((Decimal(x['price']) + Decimal(x['variant_delta'])) * x['quantity']) for x in lines]
    discounts = [ZERO for _ in lines]
    rule = case['discount']
    if rule:
        eligible = [i for i, x in enumerate(lines) if x['key'] in rule['eligible_keys']]
        eligible_gross = sum((gross[i] for i in eligible), ZERO)
        requested = (eligible_gross * Decimal(rule['value']) / Decimal(100)
                     if rule['kind'] == 'PERCENT' else Decimal(rule['value']))
        discount = money(min(requested, eligible_gross))
        if eligible_gross:
            raw = {i: discount * gross[i] / eligible_gross for i in eligible}
            for i in eligible:
                discounts[i] = raw[i].quantize(CENT, rounding=ROUND_DOWN)
            cents_remaining = int((discount - sum(discounts, ZERO)) / CENT)
            order = sorted(eligible, key=lambda i: (-(raw[i] - discounts[i]), lines[i]['key']))
            for i in order[:cents_remaining]:
                discounts[i] += CENT
    tax = sum((money((gross[i] - discounts[i]) * Decimal(rate) / Decimal(100))
               for i, line in enumerate(lines) for rate in line['tax_rates']), ZERO)
    subtotal, discount_total = sum(gross, ZERO), sum(discounts, ZERO)
    return {'subtotal': str(money(subtotal)), 'discount': str(money(discount_total)),
            'tax': str(money(tax)), 'total': str(money(subtotal - discount_total + tax)),
            'line_discounts': [str(money(x)) for x in discounts]}

def boundary(anchor: date, cadence: str, index: int) -> date:
    if cadence in {'DAILY', 'WEEKLY'}:
        return anchor + timedelta(days=index * (1 if cadence == 'DAILY' else 7))
    if cadence == 'MONTHLY':
        month_index = anchor.year * 12 + anchor.month - 1 + index
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
    elif cadence == 'YEARLY':
        year, month = anchor.year + index, anchor.month
    else:
        raise ValueError(f'Unsupported cadence: {cadence}')
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))

def main() -> None:
    require((ROOT / 'AGENTS.md').is_file(), 'Missing shared AGENTS.md')
    people = {
        'midhun-p-m': 'Midhun P M',
        'thanushree-suresh': 'Thanushree Suresh',
        'noel-biju': 'Noel Biju',
        'sherin-saji': 'Sherin Saji',
    }
    expected_roles = {ROOT / 'team' / slug / 'AGENTS.md' for slug in people}
    require(set((ROOT / 'team').glob('*/AGENTS.md')) == expected_roles,
            'Expected exactly the four named contributor role files')
    for slug, name in people.items():
        require(name in (ROOT / 'team' / slug / 'AGENTS.md').read_text(),
                f'Missing owner name in role file: {slug}')
        require((ROOT / 'handoffs' / f'{slug}.md').is_file(), f'Missing handoff for {name}')
    require(len(list((ROOT / 'prompts').glob('*.md'))) == 6, 'Expected six launch/review prompts')
    required = ['START_HERE.md', 'docs/01-MVP.md', 'docs/02-PRD.md',
                'docs/05-API-CONTRACT.md', 'docs/06-DOMAIN-RULES.md',
                'docs/09-INTEGRATION.md', 'docs/15-REQUIREMENTS.md',
                'references/Subscription_Management_System.pdf', '.env.example', '.gitignore']
    for item in required:
        require((ROOT / item).is_file(), f'Missing {item}')
    excluded = {'.git', '.venv', 'venv', 'node_modules', 'dist', '.cache', '.pytest_cache', '.ruff_cache'}
    pack_files = [p for p in ROOT.rglob('*') if p.is_file() and not (set(p.relative_to(ROOT).parts) & excluded)]
    for path in (p for p in pack_files if p.suffix == '.json'):
        json.loads(path.read_text())
    for path in (p for p in pack_files if p.suffix == '.md'):
        text = path.read_text()
        require(not re.search(r'\b[Aa]gents?\s+[1-4]\b|\bA[1-4]\b|handoffs/agent-|agents/0[1-4]-', text),
                f'Obsolete numbered team reference in {path}')
        require(not re.search(r'\b(?:agent[1-4]|midhun-p-m|thanushree-suresh|noel-biju|sherin-saji)/(?:platform|subscriptions|billing|experience)\b', text),
                f'Branch names must describe features in {path}')
        require(text.count('```') % 2 == 0, f'Unbalanced fenced code in {path}')
        require('\u2014' not in text, f'Unexpected em dash in {path}')
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', text):
            if re.match(r'^[a-zA-Z]+://', target) or target.startswith('#'):
                continue
            require((path.parent / target.split('#')[0]).exists(), f'Broken relative link in {path}: {target}')
    data = json.loads((ROOT / 'contracts/billing-vectors.json').read_text())
    for case in data['cases']:
        actual = calculate(case)
        require(actual == case['expected'], f"Fixture mismatch {case['id']}: {actual}")
        print(f"PASS arithmetic: {case['id']}")
    for case in data['cadence_cases']:
        actual = [boundary(date.fromisoformat(case['anchor']), case['cadence'], n).isoformat() for n in case['indices']]
        require(actual == case['expected'], f'Cadence mismatch: {case}')
        print(f"PASS calendar: {case['cadence']}")
    payment = data['payment_case']
    balance = Decimal(payment['invoice_total'])
    for amount, expected_balance, expected_state in zip(payment['payments'], payment['expected_balances'], payment['expected_states']):
        balance = money(balance - Decimal(amount))
        require(str(balance) == expected_balance, 'Payment balance mismatch')
        require(('PAID' if balance == 0 else 'CONFIRMED') == expected_state, 'Payment state mismatch')
    invoice = json.loads((ROOT / 'contracts/examples/invoice.json').read_text())['data']
    require(Decimal(invoice['subtotal']) - Decimal(invoice['discount_total']) + Decimal(invoice['tax_total']) == Decimal(invoice['total']), 'Invoice total mismatch')
    paid = sum((Decimal(p['amount']) for p in invoice['payments']), ZERO)
    require(paid == Decimal(invoice['paid_amount']), 'Paid amount mismatch')
    require(Decimal(invoice['total']) - paid == Decimal(invoice['balance_due']), 'Invoice balance mismatch')
    dashboard = json.loads((ROOT / 'contracts/examples/dashboard.json').read_text())['data']
    require(dashboard['cash_received_in_range'] == invoice['paid_amount'], 'Dashboard cash mismatch')
    require(dashboard['outstanding_now'] == invoice['balance_due'], 'Dashboard balance mismatch')
    print('PASS pack structure, JSON, links, payment example and invoice/dashboard consistency')
    print('Planning-pack validation only. No application, database, concurrency, email or browser tests were run.')

if __name__ == '__main__':
    main()
