"""Explicit T30 dataset, restricted to the assigned disposable PostgreSQL database.

Seed/cleanup a new mode0600 manifest directly under /tmp. No schema operations.
Do not run alongside other tests: the seed requires an empty reporting dataset.
"""

import argparse
import json
import os
import platform
import secrets
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from live_fixture import checked_engine
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    DiscountRedemption,
    EmailOutbox,
    Invoice,
    InvoiceLine,
    InvoiceLineTax,
    PasswordResetToken,
    Payment,
    Plan,
    SessionRecord,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
    User,
)

SUBSCRIPTIONS = 5000
INVOICES = 20000
BATCH = 500


def chunks(values):
    for offset in range(0, len(values), BATCH):
        yield values[offset:offset + BATCH]


def manifest_path(path):
    if path.parent != Path('/tmp') or path.is_symlink():
        raise RuntimeError('Use a private manifest directly under /tmp')


def seed(path):
    manifest_path(path)
    if path.exists():
        raise RuntimeError('Manifest already exists; cleanup its dataset first')
    engine = checked_engine()
    run = uuid4().hex[:12]
    started = time.monotonic()
    customer_ids = [uuid4(), uuid4()]
    plan_id = uuid4()
    staff_id, customer_user_id = uuid4(), uuid4()
    actors = {}
    rows = {key: [] for key in ['subscriptions', 'periods', 'invoices', 'lines', 'payments']}
    first_subscription = first_invoice = None
    with engine.begin() as connection:
        if connection.scalar(select(func.count()).select_from(Subscription)) or connection.scalar(
            select(func.count()).select_from(Invoice)
        ):
            raise RuntimeError('T30 requires an empty disposable reporting dataset')
        connection.execute(insert(Customer), [
            {'id': ident, 'display_name': f'T30 Fictional Customer {index + 1}',
             'email': f't30-{run}-{index}@example.com',
             'billing_address': {'city': 'Fictional City', 'country': 'IN'}}
            for index, ident in enumerate(customer_ids)
        ])
        connection.execute(insert(Plan), {
            'id': plan_id, 'name': 'T30 fictional monthly service', 'base_fee': Decimal('100.00'),
            'cadence': 'MONTHLY', 'available_from': date(2026, 1, 1), 'min_quantity': 1,
        })
        for key, ident, role in [('staff', staff_id, 'STAFF'),
                                 ('customer_a', customer_user_id, 'CUSTOMER')]:
            password = secrets.token_urlsafe(24) + 'Aa!'
            email = f't30-{run}-{key}@example.com'
            connection.execute(insert(User), {
                'id': ident, 'display_name': f'T30 {key}', 'normalized_email': email,
                'password_hash': hash_password(password), 'role': role,
                'customer_id': customer_ids[0] if role == 'CUSTOMER' else None,
            })
            actors[key] = {'id': str(ident), 'email': email, 'password': password}
        # Four real, nonoverlapping monthly periods per subscription. The fixed
        # test app date is November 2; all subscriptions remain active until Dec 1.
        boundaries = [date(2026, month, 1) for month in range(7, 12)]
        subs, periods, invoices, lines, payments = [], [], [], [], []
        for index in range(SUBSCRIPTIONS):
            subscription_id = uuid4()
            customer_id = customer_ids[index % 2]
            subscription_number = f'T30-S-{run}-{index:05d}'
            rows['subscriptions'].append(str(subscription_id))
            subs.append({
                'id': subscription_id, 'number': subscription_number, 'customer_id': customer_id,
                'plan_id': plan_id, 'state': 'ACTIVE', 'start_date': boundaries[0],
                'end_date': date(2026, 12, 1), 'next_cycle_index': 4, 'payment_terms_days': 14,
                'plan_snapshot': {'name': 'T30 fictional monthly service', 'cadence': 'MONTHLY',
                                  'base_fee': '100.00', 'allow_pause': False, 'allow_early_close': False,
                                  'allow_renew': False},
                'created_at': datetime(2026, 7, 1, tzinfo=UTC) + timedelta(seconds=index),
            })
            if index == 0:
                first_subscription = {'id': str(subscription_id), 'number': subscription_number}
            for cycle in range(4):
                period_id, invoice_id, line_id, payment_id = [uuid4() for _ in range(4)]
                paid = (index // 2 + cycle) % 2 == 0
                invoice_number = f'T30-I-{run}-{index:05d}-{cycle}'
                for key, ident in [('periods', period_id), ('invoices', invoice_id),
                                   ('lines', line_id), ('payments', payment_id)]:
                    rows[key].append(str(ident))
                periods.append({'id': period_id, 'subscription_id': subscription_id,
                                'cycle_index': cycle, 'period_start': boundaries[cycle],
                                'period_end': boundaries[cycle + 1], 'disposition': 'INVOICED'})
                invoices.append({
                    'id': invoice_id, 'number': invoice_number, 'subscription_id': subscription_id,
                    'billing_period_id': period_id, 'customer_id': customer_id,
                    'status': 'PAID' if paid else 'CONFIRMED', 'currency': 'INR',
                    'invoice_date': boundaries[cycle], 'due_date': boundaries[cycle] + timedelta(days=14),
                    'customer_snapshot': {'display_name': f'T30 Fictional Customer {index % 2 + 1}'},
                    'seller_snapshot': {'name': 'Brightloop Software'},
                    'subtotal': Decimal('100.00'), 'discount_total': Decimal('0.00'),
                    'tax_total': Decimal('0.00'), 'total': Decimal('100.00'),
                    'confirmed_at': datetime.combine(boundaries[cycle], datetime.min.time(), UTC),
                    'calculation_snapshot': {'fixture': 'T30', 'base_fee': '100.00', 'taxes': [],
                                             'subtotal': '100.00', 'total': '100.00'},
                })
                lines.append({'id': line_id, 'invoice_id': invoice_id, 'stable_line_key': 'BASE_FEE',
                              'description': 'Stored monthly service fee', 'quantity': 1,
                              'unit_price': Decimal('100.00'), 'gross': Decimal('100.00'),
                              'discount': Decimal('0.00'), 'taxable_amount': Decimal('100.00'),
                              'tax_total': Decimal('0.00'), 'total': Decimal('100.00'),
                              'source_snapshot': {'kind': 'BASE_FEE', 'amount': '100.00'}})
                payments.append({'id': payment_id, 'invoice_id': invoice_id, 'method': 'MANUAL',
                                 'amount': Decimal('100.00' if paid else '50.00'),
                                 'paid_on': boundaries[cycle] + timedelta(days=1), 'created_by': staff_id,
                                 'request_key': f't30-{run}-{index}-{cycle}',
                                 'request_payload_hash': '0' * 64})
                if index == 0 and cycle == 0:
                    first_invoice = {'id': str(invoice_id), 'number': invoice_number}
        for model, values in [(Subscription, subs), (BillingPeriod, periods), (Invoice, invoices),
                              (InvoiceLine, lines), (Payment, payments)]:
            for batch in chunks(values):
                connection.execute(insert(model), batch)
        counts = {}
        for model, expected in [(Subscription, SUBSCRIPTIONS), (BillingPeriod, INVOICES),
                                (Invoice, INVOICES), (InvoiceLine, INVOICES), (Payment, INVOICES)]:
            count = connection.scalar(select(func.count()).select_from(model))
            if count != expected:
                raise RuntimeError(f'{model.__tablename__}: expected {expected}, found {count}')
            counts[model.__tablename__] = count
        # Reconcile persisted money, not just row counts, before committing.
        financial = {
            'invoiced': str(connection.scalar(select(func.sum(Invoice.total)))),
            'cash': str(connection.scalar(select(func.sum(Payment.amount)))),
            'paid_invoices': connection.scalar(select(func.count()).select_from(Invoice).where(Invoice.status == 'PAID')),
            'partial_invoices': connection.scalar(select(func.count()).select_from(Invoice).where(Invoice.status == 'CONFIRMED')),
        }
        if financial != {'invoiced': '2000000.00', 'cash': '1500000.00',
                         'paid_invoices': 10000, 'partial_invoices': 10000}:
            raise RuntimeError('Persisted T30 financial reconciliation failed')
        data = {
            'test_only': True, 'kind': 'T30', 'database': 'cadentra_experience_test', 'run': run,
            'actors': actors, 'customers': [str(value) for value in customer_ids],
            'plan_id': str(plan_id), 'record_ids': rows,
            'first_subscription': first_subscription, 'first_invoice': first_invoice,
            'counts': counts, 'financial_reconciliation': financial, 'expected': {'active': 5000, 'customer_active': 2500,
                'invoiced': '2000000.00', 'cash': '1500000.00', 'outstanding': '500000.00',
                'customer_invoiced': '1000000.00', 'customer_cash': '750000.00',
                'customer_outstanding': '250000.00', 'customer_invoices': 10000},
            'seed_environment': {'python': platform.python_version(), 'platform': platform.platform(),
                                 'postgresql': connection.scalar(text('SELECT version()')),
                                 'seed_seconds': time.monotonic() - started},
        }
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(data, output)
    engine.dispose()
    print(f'Committed T30 fixture: {counts}; private manifest saved.')


def cleanup(path):
    manifest_path(path)
    if path.stat().st_mode & 0o077:
        raise RuntimeError('Manifest must have private permissions')
    data = json.loads(path.read_text())
    if (data.get('test_only') is not True or data.get('kind') != 'T30'
            or data.get('database') != 'cadentra_experience_test'):
        raise RuntimeError('Not a T30 fixture manifest')
    ids = {key: [UUID(value) for value in values] for key, values in data['record_ids'].items()}
    customers = [UUID(value) for value in data['customers']]
    users = [UUID(actor['id']) for actor in data['actors'].values()]
    engine = checked_engine()
    with Session(engine) as db, db.begin():
        # Dependents created by real read/login calls are scoped to recorded users/entities.
        for batch in chunks(users):
            db.execute(delete(AuditEvent).where(AuditEvent.actor_user_id.in_(batch)))
            db.execute(delete(SessionRecord).where(SessionRecord.user_id.in_(batch)))
            db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(batch)))
        for batch in chunks(customers + users + ids['subscriptions'] + ids['invoices'] + [UUID(data['plan_id'])]):
            db.execute(delete(AuditEvent).where(AuditEvent.entity_id.in_(batch)))
            db.execute(delete(EmailOutbox).where(EmailOutbox.aggregate_id.in_(batch)))
        for batch in chunks(ids['invoices']):
            db.execute(delete(DiscountRedemption).where(DiscountRedemption.invoice_id.in_(batch)))
        for batch in chunks(ids['lines']):
            db.execute(delete(InvoiceLineTax).where(InvoiceLineTax.invoice_line_id.in_(batch)))
        for model, key in [(Payment, 'payments'), (InvoiceLine, 'lines'), (Invoice, 'invoices'),
                           (BillingPeriod, 'periods')]:
            for batch in chunks(ids[key]):
                db.execute(delete(model).where(model.id.in_(batch)))
        for batch in chunks(ids['subscriptions']):
            db.execute(delete(SubscriptionPause).where(SubscriptionPause.subscription_id.in_(batch)))
            db.execute(delete(SubscriptionLine).where(SubscriptionLine.subscription_id.in_(batch)))
            db.execute(delete(Subscription).where(Subscription.id.in_(batch)))
        db.execute(delete(User).where(User.id.in_(users)))
        db.execute(delete(Customer).where(Customer.id.in_(customers)))
        db.execute(delete(Plan).where(Plan.id == UUID(data['plan_id'])))
    engine.dispose()
    path.unlink()
    print('Removed only T30 recorded UUIDs and the private manifest.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['seed', 'cleanup'])
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    (seed if args.operation == 'seed' else cleanup)(args.manifest)
