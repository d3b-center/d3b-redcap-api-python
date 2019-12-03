import json
import os

from d3b_redcap_api.redcap import REDCapStudy

r = REDCapStudy(
    "https://redcap.chop.edu/api/", os.getenv("REDCAP_API_TEST_PROJECT")
)


def _load_records():
    with open("tests/records.json") as rj:
        records_in = json.load(rj)
    r.set_records(records_in, overwrite=True)
    return records_in


def _delete_records(records):
    rnums = set(r["record"] for r in records)
    if rnums:
        r.delete_records(list(rnums))


def test_delete_set_get_records():
    # test delete
    _load_records()
    records = r.get_records()
    assert records != []
    _delete_records(records)
    assert r.get_records() == []

    # test get/set
    records_in = _load_records()
    records_out = r.get_records()
    r1 = sorted(tuple(sorted(r.items())) for r in records_in)
    r2 = sorted(tuple(sorted(r.items())) for r in records_out)
    assert r1 == r2
