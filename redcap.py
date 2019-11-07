import json
from collections import defaultdict

import numpy
import pandas
from d3b_utils.requests_retry import Session


def _clean(df):
    return df.replace(numpy.nan, "").astype(str)


def _default_to_regular(d):
    if isinstance(d, defaultdict):
        d = {k: _default_to_regular(v) for k, v in d.items()}
    return d


class RedcapStudy:
    def __init__(self, api_url, api_token):
        self.api = api_url
        self.api_token = api_token

    def _get_data(self, type, extra_args_dict=None):
        params = {
            "token": self.api_token,
            "content": type,
            "format": "json",
            "returnFormat": "json",
        }
        if extra_args_dict:
            params.update(extra_args_dict)
        return Session().post(self.api, data=params).text

    def _get_json(self, *args, **kwargs):
        return json.loads(self._get_data(*args, **kwargs))

    def get_redcap_version(self):
        return self._get_data("version")

    def get_project_info(self):
        return self._get_json("project")

    def get_instruments(self):
        """
        Get a tree of instrument metadata that looks like:
        {
            <instrument_name>: {
                "events": {<event_1>, <event_2>, ...},
                "fields": {
                    <field_name>: <{field_info_dict}>,
                    ...
                },
            ...
        }
        """
        store = defaultdict(  # forms
            lambda: defaultdict(dict)  # events and fields
        )
        for m in self._get_json("metadata"):
            instrument = m.pop("form_name")
            field_name = m.pop("field_name")
            store[instrument]["fields"][field_name] = m
            store[instrument]["events"] = set()

        store = _default_to_regular(store)
        for form in self._get_json("formEventMapping"):
            store[form["form"]]["events"].add(form["unique_event_name"])

        return store

    def get_selector_choice_map(self):
        store = dict()
        forms = set()
        for m in self._get_json("metadata"):
            forms.add(m["form_name"])
            if m["field_type"] in {"dropdown", "radio", "checkbox"}:
                store[m["field_name"]] = {
                    k.strip(): v.strip()
                    for k, v in map(
                        lambda x: x.split(",", 1),
                        m["select_choices_or_calculations"].split("|"),
                    )
                }
            elif m["field_type"] == "yesno":
                store[m["field_name"]] = {"1": "Yes", "0": "No"}
            elif m["field_type"] == "truefalse":
                store[m["field_name"]] = {"1": "True", "0": "False"}

        for f in forms:
            store[f + "_complete"] = {
                "2": "Complete",
                "1": "Unverified",
                "0": "Incomplete",
            }
        return store

    def _get_eav_records(self, raw=True):
        """
        This can optionally retrieve labels instead of raw, but two
        different instruments could be given the same name which are meant to
        be interpreted based on context. That may mean that we couldn't
        differentiate between the two, so we should defer translating headers
        until the very end.

        Unfortunately there's no way to independently ask for translated
        selector values (e.g. "Female" instead of "1") without also asking for
        translated headers, so asking for raw means doing a lot more work
        selectively digging through project metadata to map the selectors.
        This is made more difficult by the fact that the REDCap project
        metadata uniformly categorizes fields by their instrument name, but the
        records API doesn't report the instrument name for records that come
        from instruments that aren't repeating.
        """
        return self._get_json(
            "record",
            {
                "type": "eav",
                "rawOrLabel": "raw" if raw else "label",
                "exportSurveyFields": "false",
                "exportDataAccessGroups": "true",
            },
        )

    def get_records_tree(self):
        selector_map = self.get_selector_choice_map()

        store = defaultdict(  # events
            lambda: defaultdict(  # instruments
                lambda: defaultdict(  # subjects
                    lambda: defaultdict(  # instances
                        lambda: defaultdict(set)  # field names  # values
                    )
                )
            )
        )

        field_instruments = {
            m["field_name"]: m["form_name"] for m in self._get_json("metadata")
        }

        event_forms = defaultdict(set)
        for form in self._get_json("formEventMapping"):
            event_forms[form["unique_event_name"]].add(form["form"])

        for r in self._get_eav_records():
            event = r["redcap_event_name"]
            if event not in event_forms:  # obsolete
                continue
            subject = r["record"]
            field = r["field_name"]
            value = r["value"]
            if field in selector_map:
                value = selector_map[field][value]

            instrument = field_instruments.get(field)
            if not instrument:
                # "<instrument>_complete" fields are not considered part of the
                # instruments, so check for them separately
                for f in event_forms[event]:
                    if field == f"{f}_complete":
                        instrument = f
                        break

            if instrument not in event_forms[event]:  # obsolete
                continue

            # The API will return 1, '2', for repeat instances.
            # Note that 1 was an int and 2 was a str.
            instance = str(r.get("redcap_repeat_instance") or "1")
            if field != "study_id":
                store[event][instrument][subject][instance][field].add(value)

        return _default_to_regular(store)


def to_df(instrument):
    acc = []
    for p, es in instrument.items():
        for i, e in es.items():
            thing = {"subject": p, "instance": i}
            for k, v in e.items():
                thing[k] = "+".join(sorted(v))
            acc.append(thing)

    return _clean(pandas.DataFrame.from_records(acc))


def df_link(left, right, left_on, right_on):
    return _clean(
        left.merge(
            right,
            how="left",
            left_on=["subject", left_on],
            right_on=["subject", right_on],
        )
        .sort_values(by=["subject", left_on])
        .set_index("subject")
        .reset_index()
    )


def new_column_from_linked(
    left, right, left_on, right_on, new_col, from_cols, separator
):
    df = df_link(left, right, left_on, right_on)

    nc = None
    for c in from_cols:
        if nc is None:
            nc = df[c]
        else:
            nc = nc + separator + df[c]
    df[new_col] = nc.replace(f"^{separator}{separator}$", "", regex=True)

    return df[[new_col] + list(left.columns)]
