import json
from collections import defaultdict
from urllib.parse import unquote

from d3b_utils.requests_retry import Session


def _undefault_dict(d):
    if isinstance(d, defaultdict):
        d = {k: _undefault_dict(v) for k, v in d.items()}
    return d


class REDCapError(Exception):
    pass


# Note to future developers: This class uses get_ and set_ methods on purpose
# to control the user experience. Please don't replace them with property
# decorators. It needs to be completely unambiguous without inspecting the
# implementation that the data is somewhere else and that setting anything
# has serious consequences. This is an interface for manipulating REDCap with
# project administrative privilege, not just not just some data container.
# - Avi
class REDCapStudy:

    def __init__(self, api_url, api_token):
        self.api = api_url
        self.api_token = api_token

    def _get_response(self, content, params=None, **kwargs):
        """API request implementation

        :param content: What kind of content we're requesting to get or set
        :param params: additional parameters to send
        :raises REDCapError: REDCap returned an error status
        :return: REDCap server requests.Response object
        """
        all_params = {
            "token": self.api_token,
            "content": content,
            "format": "json",
            "returnFormat": "json",
        }
        all_params.update(params or {})
        if "data" in all_params and not isinstance(all_params["data"], str):
            all_params["data"] = json.dumps(all_params["data"])
        all_params = {k: v for k, v in all_params.items() if v is not None}
        resp = Session().post(self.api, data=all_params, **kwargs)
        if resp.status_code != 200:
            raise REDCapError(f"HTTP {resp.status_code} - {resp.text}")
        return resp

    def _get_json(self, *args, **kwargs):
        return self._get_response(*args, **kwargs).json()

    def _get_text(self, *args, **kwargs):
        return self._get_response(*args, **kwargs).text

    def get_arm_names(self):
        """Export Arm names

        :return: list of dicts with Arm numbers and names
        """
        # https://redcap.chop.edu/api/help/?content=exp_arms
        return self._get_json("arm")

    def set_arm_names(self, arms, delete_all_first=True):
        """Import Arm names or rename existing Arms

        :param delete_all_first: erase all existing Arms first before importing
        :return: number of Arms imported
        """
        # https://redcap.chop.edu/api/help/?content=imp_arms
        return self._get_json(
            "arm",
            params={
                "data": arms,
                "override": "1" if delete_all_first else "0",
                "action": "import",
            },
        )

    def get_event_metadata(self):
        """Export Event details (names, numbers, labels, offsets)

        :return: list of dicts with Event details
        """
        # https://redcap.chop.edu/api/help/?content=exp_metadata
        return self._get_json("event")

    def set_event_metadata(self, events, delete_all_first=True):
        """Import Event details (names, numbers, labels, offsets)

        :param events: see get_event_metadata return
        :param delete_all_first: erase all existing Events first before importing
        :return: number of Events imported
        """
        # https://redcap.chop.edu/api/help/?content=imp_metadata
        return self._get_json(
            "event",
            params={
                "action": "import",
                "override": "1" if delete_all_first else "0",
            },
        )

    def get_field_export_names(self):
        """Export mappings of field names and selected values to exported names

        :return: list of dicts of field choices
        """
        # https://redcap.chop.edu/api/help/?content=exp_field_names
        return self._get_json("exportFieldNames")

    def _act_file(
        self,
        action,
        record,
        field,
        event=None,
        repeat_instance=None,
        file_data=None,
    ):
        params = {
            "action": action,
            "record": record,
            "field": field,
            "event": event,
            "repeat_instance": repeat_instance,
        }
        return self._get_response("file", params, files=file_data)

    def get_file(self, record, field, event=None, repeat_instance=None):
        """Export a File from a file upload field on a record

        :param record: the record ID the file is attached to
        :param field: the name of field with the file
        :param event: event name if longitudinal
        :param repeat_instance: which instance if instrument/event is repeating
        :return: dict with "filename" str and "body" bytes
        """
        # https://redcap.chop.edu/api/help/?content=exp_file
        resp = self._act_file("export", record, field, event, repeat_instance)
        file_name = (
            unquote(
                resp.headers["Content-Type"].split('name="')[1].split('";')[0]
            )
            .encode("latin1")
            .decode("utf-8")
        )
        return {"body": resp.content, "filename": file_name}

    def set_file(
        self,
        filename,
        file_obj,
        record,
        field,
        event=None,
        repeat_instance=None,
    ):
        """Attach a File to a file upload field on a record

        :param filename: name of the file to create
        :param file_obj: contents of or read object for the file
        :param record: the record ID the file is attached to
        :param field: the name of field with the file
        :param event: event name if longitudinal
        :param repeat_instance: which instance if instrument/event is repeating
        """
        # https://redcap.chop.edu/api/help/?content=imp_file
        self._act_file(
            "import",
            record,
            field,
            event,
            repeat_instance,
            {"file": (filename, file_obj)},
        )

    def delete_file(self, record, field, event=None, repeat_instance=None):
        """Delete a File from a file upload field on a record

        :param record: the record ID the file is attached to
        :param field: the name of field with the file
        :param event: event name if longitudinal
        :param repeat_instance: which instance if instrument/event is repeating
        """
        # https://redcap.chop.edu/api/help/?content=del_file
        self._act_file(
            action="delete",
            record=record,
            field=field,
            event=event,
            repeat_instance=repeat_instance,
        )

    def get_redcap_version(self):
        """Get the version of REDCap as a string"""
        # https://redcap.chop.edu/api/help/?content=exp_rc_v
        return self._get_text("version")

    def get_project_info(self):
        """Get basic project attributes such as title, logitudinality,
        if surveys are enabled, creation time, etc."""
        return self._get_json("project")

    def set_project_info(self, project_info):
        """Set basic project attributes such as title, logitudinality,
        if surveys are enabled, creation time, etc."""
        # https://redcap.chop.edu/api/help/?content=imp_proj_sett
        return self._get_json(
            "project_settings", params={"data": project_info}
        )

    def get_project_xml(
        self,
        metadata_only=True,
        include_data_access_groups=True,
        include_survey_fields=True,
        include_files=True,
    ):
        """Fetch the entire project as a special XML file in CDISC ODM format.

        :param metadata_only: Don't include any of the record data
        :param include_data_access_groups: Include the redcap_data_access_group
            field in data (does nothing if metadata_only is True)
        :param include_survey_fields: Include survey identifier fields in data
            (does nothing if metadata_only is True)
        :param include_files: Include file_upload and signature fields in data
            (does nothing if metadata_only is True)

        :return: string contents of an XML file
        """
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
        """List user information with privileges, email address, and names"""
        return self._get_json("user")

    def set_users(self, users):
        """Set or update user privileges, email address, and names

        :param users: see output of get_users
        :return: number of users added or updated
        """
        return self._get_json("user", {"data": users})

    def get_data_dictionary(self):
        """Get the instrument definition information."""
        return self._get_json("metadata")

    def set_data_dictionary(self, data_dictionary):
        """Set the instrument definitions.

        :param data_dictionary: see output of get_data_dictionary
        :return: number of fields imported
        """
        return self._get_json("metadata", {"data": data_dictionary})

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
        for m in self.get_data_dictionary():
            instrument = m.pop("form_name")
            field_name = m.pop("field_name")
            store[instrument]["fields"][field_name] = m
            store[instrument]["events"] = set()

        store = _undefault_dict(store)
        for form in self.get_instrument_event_mappings():
            store[form["form"]]["events"].add(form["unique_event_name"])

        return store

    def _records_getter(
        self,
        content,
        raw=True,
        raw_headers=True,
        checkbox_labels=False,
        params=None,
    ):
        args = {
            "rawOrLabel": "raw" if raw else "label",
            "rawOrLabelHeaders": "raw" if raw_headers else "label",
            "exportCheckboxLabel": "true" if checkbox_labels else "false",
        }
        args.update(params or {})
        return self._get_json(content, params=args)

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
            params={
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
        self._get_json("record", params=args)

    def get_repeating_forms_events(self):
        self._get_json("repeatingFormsEvents")

    def set_repeating_forms_events(self, rfe):
        self._get_json("repeatingFormsEvents", params={"data": rfe})

    def get_report_records(
        self, report_id, raw=True, raw_headers=True, checkbox_labels=False
    ):
        return self._records_getter(
            "report",
            raw=raw,
            raw_headers=raw_headers,
            checkbox_labels=checkbox_labels,
            params={"report_id": report_id},
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
        for m in self.get_data_dictionary():
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

        field_forms = {
            m["field_name"]: m["form_name"] for m in self.get_data_dictionary()
        }
        # "<instrument>_complete" fields are not considered part of the
        # instruments, so include them specially
        for inst in set(field_forms.values()):
            field_forms[f"{inst}_complete"] = inst

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

        errors = defaultdict(list)

        for r in self.get_records(
            type="eav",
            raw=True,
            raw_headers=True,
            checkbox_labels=False,
            survey_fields=True,
            data_access_groups=True,
        ):
            event = r["redcap_event_name"]
            subject = r["record"]
            field = r["field_name"]
            value = r["value"]
            form = field_forms.get(field)

            def record_error(what):
                errors[what].append({
                    "event": event, "subject": subject, "field": field,
                    "value": value, "form": form
                })

            if event not in event_forms:  # obsolete
                record_error("event is missing")
                continue

            mapped_value = value
            if field in selector_map:
                if value not in selector_map[field]:  # obsolete
                    if value in selector_map[field].values():
                        record_error("choice value as text")
                    else:
                        record_error("choice value is missing")
                    continue
                mapped_value = selector_map[field][value]

            if field not in field_forms:  # obsolete
                record_error("field not in a form")
                continue

            if form not in event_forms[event]:  # obsolete
                record_error("form not in given event")
                continue

            # The API will return 1, '2', for repeat instances.
            # Note that 1 was an int and 2 was a str.
            instance = str(r.get("redcap_repeat_instance") or "1")
            if field != "study_id":
                store[event][form][subject][instance][field].add(mapped_value)


        return _undefault_dict(store), _undefault_dict(errors)
