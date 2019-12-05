import numpy
from pandas import DataFrame


def _clean(df):
    return df.replace(numpy.nan, "").astype(str)


def to_df(instrument):
    """
    Converts a `get_records_tree()[event][instrument]` to a pandas DataFrame
    """
    acc = []
    for p, es in instrument.items():
        for i, e in es.items():
            thing = {"subject": p, "instance": i}
            for k, v in e.items():
                thing[k] = "+".join(sorted(v))
            acc.append(thing)

    return _clean(DataFrame.from_records(acc))


def new_column_from_linked(
    df, other_df, df_on, other_on, new_col_name, from_col_names, separator
):
    """
    Create a new column in pandas DataFrame df that semantically references
    entries in other_df
    """
    joined_df = _clean(
        df.merge(
            other_df,
            how="left",
            left_on=["subject", df_on],
            right_on=["subject", other_on],
        )
        .sort_values(by=["subject", df_on])
        .set_index("subject")
        .reset_index()
    )

    nc = None
    for c in from_col_names:
        if nc is None:
            nc = joined_df[c]
        else:
            nc = nc + separator + joined_df[c]
    joined_df[new_col_name] = nc.replace(
        f"^{separator}{separator}$", "", regex=True
    )

    return joined_df[[new_col_name] + list(df.columns)]
