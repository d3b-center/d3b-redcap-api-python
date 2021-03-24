from numpy import nan
from pandas import DataFrame


def to_df(records_tree, event_name, instrument_name):
    """
    Converts a `get_records_tree()[event][instrument]` to a pandas DataFrame
    """
    # get records
    instrument = records_tree[event_name][instrument_name]

    # convert records to dataframe rows
    acc = []
    for p, es in instrument.items():
        for i, e in es.items():
            entry = {"subject": p, f"subject_{instrument_name}_instance": i}
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
    return df.replace(nan, "").astype(str)


def summary_column(df, from_col_names, separator):
    """
    Create a delimited summary column from multiple columns.
    """
    nc = df[from_col_names].apply(lambda r: separator.join(r), axis=1)
    return nc.replace(f"^{separator}{separator}$", "", regex=True)
