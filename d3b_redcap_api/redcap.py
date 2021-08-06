import json
import re
from collections import defaultdict
from urllib.parse import unquote

from d3b_utils.requests_retry import Session


def _undefault_dict(d):
    if isinstance(d, dict):
        d = {k: _undefault_dict(v) for k, v in d.items()}
    if isinstance(d, set):
        return sorted(d)
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
        resp = Session(status_forcelist=(502, 503, 504)).post(
            self.api, data=all_params, **kwargs
        )
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

    def get_instrument_labels(self):
        """Export mappings of instrument internal names to their display labels

        :return: list of dicts with instrument_name and instrument_label keys
        """
        return self._get_json("instrument")

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
        return self._get_json("project_settings", params={"data": project_info})

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

        for form in self.get_instrument_event_mappings():
            store[form["form"]]["events"].add(form["unique_event_name"])

        return _undefault_dict(store)

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

    def get_subjects(self):
        """Get the list of record subject IDs"""
        id_field = self.get_data_dictionary()[0]["field_name"]
        id_records = self._records_getter("record", params={"fields": id_field})
        return list({e[id_field] for e in id_records})

    def get_records(
        self,
        type="eav",
        raw=True,
        raw_headers=True,
        checkbox_labels=False,
        survey_fields=True,
        data_access_groups=True,
        fields=None,
    ):
        """Returns all data from the study without restructuring"""
        remaining_subjects = self.get_subjects()
        batch_size = len(remaining_subjects)
        print(f"Found {batch_size} subjects.")
        records = []
        while remaining_subjects:
            batch = remaining_subjects[:batch_size]
            print(f"Requesting {len(batch)} subjects...")
            params = {
                "type": type,
                "exportSurveyFields": "true" if survey_fields else "false",
                "exportDataAccessGroups": "true"
                if data_access_groups
                else "false",
            }
            for i, r in enumerate(batch):
                params[f"records[{i}]"] = r

            if fields:
                for i, f in enumerate(fields):
                    params[f"fields[{i}]"] = f

            try:
                records.extend(
                    self._records_getter(
                        "record",
                        raw=raw,
                        raw_headers=raw_headers,
                        checkbox_labels=checkbox_labels,
                        params=params,
                    )
                )
                remaining_subjects = remaining_subjects[batch_size:]
            except REDCapError as e:
                if str(e).startswith(("HTTP 400", "HTTP 500")):
                    print("Reducing batch size and trying again...")
                    batch_size = int(0.5 + (batch_size / 2))
                else:
                    print(str(e))
                    return

        if type == "eav":
            id_field = self.get_data_dictionary()[0]["field_name"]
            records = [r for r in records if r["field_name"] != id_field]
        return records

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
        return self._get_json("record", params=args)

    def delete_records(self, record_name_list, arm=None):
        args = {"action": "delete"}
        for i, r in enumerate(record_name_list):
            args[f"records[{i}]"] = r
        if arm is not None:
            args["arm"] = arm
        return self._get_json("record", args)

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
        """Returns a map for every field that needs translation from index to
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

    def get_records_tree(self, debug_type="flat", raw_selectors=False):
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
        # this is where we'll store all the data
        store = defaultdict(  # events
            lambda: defaultdict(  # instruments
                lambda: defaultdict(  # subjects
                    lambda: defaultdict(  # instances
                        lambda: defaultdict(set)  # field names  # values
                    )
                )
            )
        )

        data_dict = self.get_data_dictionary()
        record_id_field = data_dict[0]["field_name"]
        field_forms = {m["field_name"]: m["form_name"] for m in data_dict}
        # "<instrument>_complete" fields are not considered part of the
        # instruments, so include them specially
        for inst in set(field_forms.values()):
            field_forms[f"{inst}_complete"] = inst

        event_forms = defaultdict(set)
        for iem in self.get_instrument_event_mappings():
            event_forms[iem["unique_event_name"]].add(iem["form"])

        selector_map = self.get_selector_choice_map()

        # We could retrieve labels instead of raw, but two different
        # instruments could be given the same name which are meant to be
        # interpreted based on context. That may mean that we couldn't
        # differentiate between the two, so we should defer translating headers
        # until the very end.
        #
        # [Nov 2019] Unfortunately there's no way to independently ask for
        # translated selector values (e.g. "Female" instead of "1") without
        # also asking for translated headers, so asking for raw means doing a
        # lot more work selectively digging through project metadata to map the
        # selectors. This is made more difficult by the fact that the REDCap
        # project metadata uniformly categorizes fields by their instrument
        # name, but the records API doesn't report the instrument name for
        # records that come from instruments that aren't repeating. Maybe that
        # will change, but this code would probably keep working anyway.

        errors = defaultdict(list)
        all_subjects = set()
        for r in self.get_records(
            type=debug_type,
            raw=True,
            raw_headers=True,
            checkbox_labels=False,
            survey_fields=True,
            data_access_groups=True,
        ):

            def _check_errors_and_store_mapped():
                def _record_error(what):
                    errors[what].append(
                        {
                            "event": event,
                            "subject": subject,
                            "field": field,
                            "value": value,
                            "form": form,
                        }
                    )

                mapped_value = value
                if (
                    (not raw_selectors)
                    and (field in selector_map)
                    and (value != "")
                ):
                    if value not in selector_map[field]:  # obsolete
                        if value in selector_map[field].values():
                            _record_error("choice value as text")
                        else:
                            _record_error("choice value is missing")
                        return False
                    mapped_value = selector_map[field][value]
                if event not in event_forms:  # obsolete
                    _record_error("event is missing")
                    return False
                if field not in (
                    {"redcap_data_access_group"} | set(field_forms)
                ):  # obsolete
                    _record_error("field not in a form")
                    return False
                if form not in event_forms[event]:  # obsolete
                    _record_error("form not in given event")
                    return False
                if field != record_id_field:
                    if field == f"{form}_complete":
                        store[event][form][subject][instance][field] = {
                            mapped_value
                        }
                    else:
                        store[event][form][subject][instance][field].add(
                            mapped_value
                        )
                return True

            event = r.pop("redcap_event_name")

            # The API will return 1, "2", for repeat instances.
            # Note that 1 was an int and 2 was a str.
            # The API can also return "" or nothing at all.
            instance = str(r.pop("redcap_repeat_instance", "1") or "1")

            # This is only populated for repeat instruments, because the REDCap
            # motto is "Why do the same thing all the time when we could do
            # something different every time?"
            repeat_form = r.pop("redcap_repeat_instrument", None)

            if debug_type == "eav":
                subject = r["record"]
                all_subjects.add(subject)

                field = r["field_name"]
                value = r["value"]
                form = repeat_form or field_forms.get(field)

                if not _check_errors_and_store_mapped():
                    continue
            else:
                subject = r.pop(record_id_field)
                all_subjects.add(subject)

                for field, value in r.items():
                    form = repeat_form or field_forms.get(field)

                    if re.search(r"___\d+$", field):  # probably checkboxes
                        real_field, real_value = field.rsplit("___", 1)
                        if real_field in selector_map:  # definitely checkboxes
                            if value == "0":
                                continue  # checkbox not selected
                            if value == "":
                                continue  # checkbox not present

                            field = real_field
                            value = real_value
                            form = field_forms.get(field)

                    if (value == "") and (form not in event_forms[event]):
                        continue  # field not present

                    if not _check_errors_and_store_mapped():
                        continue

        # Should unused forms and fields be represented too for completeness?
        # Let's mark them as present and empty but incomplete.
        form_fields = defaultdict(set)
        for field, form in field_forms.items():
            form_fields[form].add(field)

        for event_name, event_form_names in event_forms.items():
            for form_name in event_form_names:
                for subject in all_subjects:
                    if not store[event_name][form_name][subject]:
                        store[event_name][form_name][subject] = {"1": dict()}
                    for i, iv in store[event_name][form_name][subject].items():
                        for field in form_fields[form_name]:
                            if field not in iv:
                                if field == f"{form_name}_complete":
                                    iv[field] = {"Incomplete"}
                                else:
                                    iv[field] = {""}

        return _undefault_dict(store), _undefault_dict(errors)
