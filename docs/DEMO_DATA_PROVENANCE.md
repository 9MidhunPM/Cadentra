# Commerce demo data provenance

This package prepares a catalog subset. It does not populate any database or
change existing records. The coordinator owns the separate importer, target
confirmation and supported-service financial replay.

The catalog is adapted from **Chen, D. (2015), Online Retail**, UCI Machine
Learning Repository, DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33).
The [official dataset record](https://archive.ics.uci.edu/dataset/352/online%2Bretail)
licenses it under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
The source contains historical transactions from a UK gift retailer; its monetary
prices are in sterling. Cadentra does not import or relabel those prices as INR.
The source's creator and UCI do not endorse this demo.

## Retained and generated information

The committed manifest is
[`backend/app/demo_data/online_retail_catalog.json`](../backend/app/demo_data/online_retail_catalog.json).
It contains exactly 80 product entries, retaining only source `StockCode` and
`Description` plus a normalized display name. Source customer identifiers,
countries, order identifiers, order dates, quantities and prices are excluded.
Raw source files remain outside Git in a private temporary folder.

**All Cadentra INR prices, costs, variants, plans, customer identities, contacts,
subscriptions, invoices and payments are fictional demo scenarios.** They are
neither actual retailer transactions nor currency conversions. Any later importer
must identify this cohort as demo data, preserve existing records and prevent
emails to its fictional contacts. This catalog preparation command creates no
users, contacts, financial records or outbox messages.

## Source integrity

Downloaded from the [official UCI ZIP](https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip)
on **2026-10-31 at 10:04:16 UTC**.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `online-retail.zip` | 23715478 | `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b` |
| `Online Retail.xlsx` | 23715344 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |

The ZIP contains the single workbook `Online Retail.xlsx`. The preparation
script checks the archive member and expected B/C column headers before reading
only product codes and descriptions. Source hashes are included in the manifest.
A changed source must be reviewed as a new provenance revision.

## Deterministic selection and modifications

[`scripts/prepare_commerce_catalog.py`](../scripts/prepare_commerce_catalog.py)
performs this offline selection:

1. Accept stock codes matching `[0-9]{5}[A-Z]*`. Trim source descriptions; reject
   blank, short, oversized, control-character or question-mark entries and
   descriptions of adjustments, services, charges or damaged/missing stock. The
   exact exclusion expression is retained in the script.
2. Count eligible description occurrences per stock code. Select the 80 highest
   counts, breaking ties by ascending stock code. This ranks description
   occurrences, not sales value or quantity.
3. Choose the most frequent eligible description per stock code, with ascending
   exact description text as the tie-breaker. Keep that trimmed source text in
   `original_description`.
4. Collapse display whitespace and apply Python `str.title()` for the `name`.
   Preserve source stock codes unchanged. No customer or order fields enter the
   output.

The committed manifest freezes this selection so ordinary demo imports require
neither internet access nor spreadsheet libraries.

## Reproduce the manifest

Run from the repository root. Use a preparation environment with `openpyxl`
installed (prepared with Python 3.14.8 and openpyxl 3.1.5); this is **not** a backend
runtime dependency. Keep the downloaded ZIP
under a private `/tmp/cadentra-commerce-source` directory, outside the checkout.
The command below performs no network or database operation:

```bash
python scripts/prepare_commerce_catalog.py \
  --source-archive /tmp/cadentra-commerce-source/online-retail.zip \
  --retrieved-at 2026-10-31T10:04:16Z \
  --count 80 \
  --output /tmp/cadentra-commerce-source/reproduced-catalog.json
cmp backend/app/demo_data/online_retail_catalog.json \
  /tmp/cadentra-commerce-source/reproduced-catalog.json
```

Use the recorded timestamp when reproducing this revision; record the actual new
retrieval timestamp and hashes for a new source revision. The script deliberately
does not download source files or overwrite source records automatically.

## Attribution for the deployed demo

Retain this notice in the manifest and make it accessible from the populated
demo through a provenance notice/link when the importer is integrated:

> Catalog descriptions adapted from Chen, D. (2015), *Online Retail*, UCI Machine
> Learning Repository, DOI:10.24432/C5BW33. Licensed CC BY 4.0. Descriptions were
> selected and normalized; prices, customers and financial scenarios are fictional
> Cadentra demo data. No endorsement is implied.

Include links to the official dataset and licence. This file and the prepared
manifest retain attribution and disclose modifications; integration must not
present the generated customer or financial scenarios as genuine source data.

## Coordinator import-date decision

The explicit public demo import creates fictional six-month history by replaying
ordinary subscription/billing/payment services under a context-scoped historical
Clock in one privileged CLI process. It never updates invoice dates/snapshots after
creation, changes the host/API/worker clock, or exposes clock selection over HTTP.
Only the imported namespace is replayed. The Cadentra worker is temporarily paused
during that bounded replay to prevent concurrent catch-up, then restarted.
Existing active global discount rules must be rejected by preflight if they could
consume uses or alter existing history; no global billing/lifecycle sweep is run.
All imported customers carry a durable no-email provenance marker, with reserved
example.com contact addresses and pre-enqueue/dispatch suppression. A separately
authorized reset test to the user's own address is outside that fictional cohort.
