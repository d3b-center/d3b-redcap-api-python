from collections import Counter

from numpy import nan
from pandas import DataFrame


def to_df(records_tree, event_name, instrument_name):
    """
    Converts a `get_records_tree()[event][instrument]` to a pandas DataFrame
    """
    # get instrument records
    records = records_tree[event_name][instrument_name]

    # build dataframe rows from records
    acc = []
    for s, entries in records.items():
        for i, e in entries.items():
            entry = {"subject": s, f"subject_{instrument_name}_instance": i}
            entry.update({k: "+".join(sorted(v)) for k, v in e.items()})
            acc.append(entry)
    df = DataFrame(acc)

    # drop rows that are empty in important (not unimportant) fields
    unimportant = {
        "subject",
        f"subject_{instrument_name}_instance",
        f"{instrument_name}_complete",
    }
    df = df.dropna(how="all", subset=df.columns.difference(unimportant))
    return df


def all_dfs(records_tree):
    """
    Calls to_df on every instrument found in the records tree and returns a
    dict keyed by the instrument name if the instrument name is unique or
    by event_instrument if not.
    """
    names = [i for instruments in records_tree.values() for i in instruments]
    reused = {k for k, v in Counter(names).items() if v > 1}

    dfs = {}
    for e, event_instruments in records_tree.items():
        for i in event_instruments:
            dfs[f"{e}_{i}" if i in reused else i] = to_df(records_tree, e, i)

    return dfs


def summary_column(df, from_col_names, separator):
    """
    Create a delimited summary column from multiple columns.
    """
    nc = df[from_col_names].apply(lambda r: separator.join(r), axis=1)
    return nc.replace(f"^{separator}{separator}$", "", regex=True)
