"""The one-shot CLI owns its transaction and prints counters only."""
import json
from unittest.mock import MagicMock

import pytest

from app.core import outbox


def test_cli_commits_one_batch_and_prints_only_counts(monkeypatch, capsys):
    factory = MagicMock()
    db = factory.begin.return_value.__enter__.return_value
    monkeypatch.setattr("app.db.session.SessionFactory", factory)
    dispatch = MagicMock(return_value={"processed": 2, "accepted_by_smtp": 2, "failed": 0,
                                      "private_future_field": "must-never-print"})
    monkeypatch.setattr(outbox, "dispatch_pending", dispatch)
    assert outbox.main(["--once", "--limit", "7"]) == 0
    dispatch.assert_called_once_with(db, 7)
    factory.begin.assert_called_once_with()
    factory.begin.return_value.__exit__.assert_called_once_with(None, None, None)
    assert json.loads(capsys.readouterr().out) == {
        "processed": 2, "accepted_by_smtp": 2, "failed": 0,
    }


def test_cli_reports_failed_batch_nonzero(monkeypatch, capsys):
    monkeypatch.setattr("app.db.session.SessionFactory", MagicMock())
    monkeypatch.setattr(outbox, "dispatch_pending", lambda db, limit: {
        "processed": 1, "accepted_by_smtp": 0, "failed": 1,
    })
    assert outbox.main(["--once"]) == 1
    assert json.loads(capsys.readouterr().out)["failed"] == 1


@pytest.mark.parametrize("args", [[], ["--once", "--limit", "0"], ["--once", "--limit", "1001"]])
def test_cli_requires_explicit_valid_batch(args):
    with pytest.raises(SystemExit) as error:
        outbox.main(args)
    assert error.value.code == 2
