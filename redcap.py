import json
from collections import defaultdict
from urllib.parse import unquote

from d3b_utils.requests_retry import Session


def _undefault_dict(d):
    if isinstance(d, defaultdict):
        d = {k: _undefault_dict(v) for k, v in d.items()}
    return d


class RedcapError(Exception):
    pass


class RedcapStudy:
    """
    Note to future developers: This class uses get_ and set_ methods on purpose
    to control the user experience. Please don't replace them with property
    decorators. It needs to be completely unambiguous without inspecting the
    implementation that the data is somewhere else and that setting anything
    has serious consequences. This is an interface for manipulating REDCap with
    project administrative privilege, not just not just some data container.
    - Avi
    """

    def __init__(self, api_url, api_token):
        self.api = api_url
        self.api_token = api_token

    def _get_response(self, type, extra_args=None):
        params = {
            "token": self.api_token,
            "content": type,
            "format": "json",
            "returnFormat": "json",
        }
        params.update(extra_args or {})
        if "data" in params and not isinstance(params["data"], str):
            params["data"] = json.dumps(params["data"])
        resp = Session().post(self.api, data=params)
        if resp.status_code != 200:
            raise RedcapError(f"HTTP {resp.status_code} - {resp.json()}")
        return resp

    def _get_json(self, *args, **kwargs):
        return self._get_response(*args, **kwargs).json()

    def _get_text(self, *args, **kwargs):
        return self._get_response(*args, **kwargs).text

    def get_arms(self):
        return self._get_json("arm")

    def set_arms(self, arms, delete_all_first=True):
        return self._get_json(
            "arm",
            extra_args={
                "data": arms,
                "override": "1" if delete_all_first else "0",
                "action": "import",
            },
        )

    def get_events(self):
        return self._get_json("event")

    def set_events(self, events, delete_all_first=True):
        return self._get_json(
            "event",
            extra_args={
                "action": "import",
                "override": "1" if delete_all_first else "0",
            },
        )

    def get_field_export_names(self):
        return self._get_json("exportFieldNames")

    def _act_file(
        self, action, record, field, event=None, repeat_instance=None
    ):
        args = {"action": action, "record": record, "field": field}
        if event is not None:
            args["event"] = event
        if repeat_instance is not None:
            args["repeat_instance"] = repeat_instance
        return self._get_response("file", args)

    def get_file(self, record, field, event=None, repeat_instance=None):
        resp = self._act_file("export", record, field, event, repeat_instance)
        file_name = (
            resp.headers["Content-Type"].split('name="')[1].split('";')[0]
        )
        file_name = unquote(file_name).encode("latin1").decode("utf-8")
        return {"body": resp.content, "filename": file_name}

    def set_file(self, record, field, event=None, repeat_instance=None):
        return self._act_file(
            "import", record, field, event, repeat_instance
        ).json()

    def delete_file(self, record, field, event=None, repeat_instance=None):
        return self._act_file(
            "delete", record, field, event, repeat_instance
        ).json()

    def get_redcap_version(self):
        return self._get_text("version")

    def get_project_info(self):
        return self._get_json("project")

    def set_project_info(self, project_info):
        return self._get_json(
            "project_settings", extra_args={"data": project_info}
        )

    def get_project_xml(
        self,
        metadata_only=True,
        include_data_access_groups=True,
        include_survey_fields=True,
        include_files=True,
    ):
        return self._get_text(
            "project_xml",
            {
                "returnMetadataOnly": metadata_only,
                "exportDataAccessGroups": include_data_access_groups,
                "exportSurveyFields": include_survey_fields,
                "exportFiles": include_files,
            },
        )

    def get_users(self):
        return self._get_json("user")

    def set_users(self, users):
        return self._get_json("user", {"data": users})

    def get_metadata(self):
        return self._get_json("metadata")

    def set_metadata(self, metadata):
        return self._get_json("metadata", {"data": metadata})

    def get_instrument_event_mappings(self):
        return self._get_json("formEventMapping")

    def set_instrument_event_mappings(self, iem):
        return self._get_json("formEventMapping", {"data": iem})

    def create_project(self, project_data):
        raise NotImplementedError()  # TODO

    def get_instrument_tree(self):
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
        for m in self.get_metadata():
            instrument = m.pop("form_name")
            field_name = m.pop("field_name")
            store[instrument]["fields"][field_name] = m
            store[instrument]["events"] = set()

        store = _undefault_dict(store)
        try:
            for form in self.get_instrument_event_mappings():
                store[form["form"]]["events"].add(form["unique_event_name"])
        except RedcapError:
            pass

        return store

    def _records_getter(
        self,
        content,
        raw=True,
        raw_headers=True,
        checkbox_labels=False,
        extra_args=None,
    ):
        args = {
            "rawOrLabel": "raw" if raw else "label",
            "rawOrLabelHeaders": "raw" if raw_headers else "label",
            "exportCheckboxLabel": "true" if checkbox_labels else "false",
        }
        args.update(extra_args or {})
        return self._get_json(content, extra_args=args)

    def get_records(
        self,
        type="eav",
        raw=True,
        raw_headers=True,
        checkbox_labels=False,
        survey_fields=True,
        data_access_groups=True,
    ):
        return self._records_getter(
            "record",
            raw=raw,
            raw_headers=raw_headers,
            checkbox_labels=checkbox_labels,
            extra_args={
                "type": type,
                "exportSurveyFields": "true" if survey_fields else "false",
                "exportDataAccessGroups": "true"
                if data_access_groups
                else "false",
            },
        )

    def set_records(
        self, records, type="eav", overwrite=False, auto_number=False
    ):
        args = {
            "type": type,
            "data": records,
            "overwriteBehavior": "overwrite" if overwrite else "normal",
            "forceAutoNumber": "true" if auto_number else "false",
        }
        if auto_number:
            args["returnContent"] = "auto_ids"
        self._get_json("record", extra_args=args)

    def get_repeating_forms_events(self):
        self._get_json("repeatingFormsEvents")

    def set_repeating_forms_events(self, rfe):
        self._get_json("repeatingFormsEvents", extra_args={"data": rfe})

    def get_report_records(
        self, report_id, raw=True, raw_headers=True, checkbox_labels=False
    ):
        return self._records_getter(
            "report",
            raw=raw,
            raw_headers=raw_headers,
            checkbox_labels=checkbox_labels,
            extra_args={"report_id": report_id},
        )

    def get_selector_choice_map(self):
        """
        Returns a map for every field that needs translation from index to
        value:
        {
            <field_name>: {
                <index>: <value>,
                ...
            },
            ...
        }
        """
        store = dict()
        forms = set()
        for m in self.get_metadata():
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

    def get_records_tree(self):
        """Returns all data from the study in the nested form:
        {
            <event_name>: {            # event data
                <instrument_name>: {   # instrument data
                    <record_id>: {     # subject data for this event+instrument
                        <instance>: {  # subject event+instrument instance
                            <field>: set(), # field values
                            ...
                        },
                        ...
                    },
                    ...
                },
                ...
            },
            ...
        }
        """
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
            m["field_name"]: m["form_name"] for m in self.get_metadata()
        }
        event_forms = defaultdict(set)
        for form in self._get_json("formEventMapping"):
            event_forms[form["unique_event_name"]].add(form["form"])

        selector_map = self.get_selector_choice_map()

        # We could retrieve labels instead of raw, but two different
        # instruments could be given the same name which are meant to be
        # interpreted based on context. That may mean that we couldn't
        # differentiate between the two, so we should defer translating headers
        # until the very end.
        #
        # Unfortunately there's no way to independently ask for translated
        # selector values (e.g. "Female" instead of "1") without also asking
        # for translated headers, so asking for raw means doing a lot more work
        # selectively digging through project metadata to map the selectors.
        # This is made more difficult by the fact that the REDCap project
        # metadata uniformly categorizes fields by their instrument name, but
        # the records API doesn't report the instrument name for records that
        # come from instruments that aren't repeating.

        for r in self.get_records(
            type="eav",
            raw=True,
            raw_headers=True,
            checkbox_labels=False,
            survey_fields=True,
            data_access_groups=True,
        ):
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

        return _undefault_dict(store)
