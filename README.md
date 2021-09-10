<p align="center">
  <img alt="Logo for The Center for Data Driven Discovery" src="docs/_media/logo.svg" width="400px" />
</p>
<p align="center">
  <a href="https://github.com/d3b-center/d3b-redcap-api-python/blob/master/LICENSE"><img src="https://img.shields.io/github/license/d3b-center/d3b-redcap-api-python.svg?style=for-the-badge"></a>
  <a href="https://circleci.com/gh/d3b-center/d3b-redcap-api-python"><img src="https://img.shields.io/circleci/project/github/d3b-center/d3b-redcap-api-python.svg?style=for-the-badge"></a>
  <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black ----line--length 80-000000.svg?style=for-the-badge"></a>
</p>

# REDCap API in Python

## Description

Supports structured data extraction for REDCap projects. The API module
`d3b_redcap_api.redcap.REDCapStudy` can be logically divided into three parts...

### Part 1: The low level interface

These are generic request/response handlers implemented here because there's no
"official" Python SDK from Vanderbilt for the REDCap API, and the closest thing
there is (https://github.com/redcap-tools/PyCap) wasn't being actively
maintained when I wanted it.

*(If someone wants to replace this part using PyCap at some point, go ahead.
Just don't break any of Part 3 in the process.)*

**Functions:** `_get_response`, `_get_json`, `_get_text`, `_act_file`

### Part 2: API functions

With the exception of `get_records`, which semi-intelligently retrieves records
in batches instead of all at once to evade server errors from response
timeouts, these all mirror the same/similarly named commands described in the
REDCap API documentation at `https://<your_redcap_server>/api/help/`. For CHOP
users that would be https://redcap.chop.edu/api/help.

*(If someone wants to replace this part using PyCap at some point, go ahead.
Just don't break any of Part 3 in the process.)*

**Functions:** 

| Getters | Setters | Deleters |
|---------|---------|----------|
|`get_arm_names` (Export Arms)|`set_arm_names` (Import Arms))|NA|
|`get_event_metadata` (Export Events)|`set_event_metadata` (Import Events)|NA|
|`get_instrument_labels` (Export Instruments)|NA|NA|
|`get_field_export_names` (Export List of Export Field Names)|NA|NA|
|`get_file` (Export a File)|`set_file` (Import a File)|`delete_file` (Delete a File)|
|`get_redcap_version` (Export REDCap Version)|NA|NA|
|`get_project_info` (Export Project Info)|`set_project_info` (Import Project Info)|NA|
|`get_project_xml` (Export Project XML)|NA|NA|
|`get_users` (Export Users)|`set_users` (Import Users)|NA|
|`get_data_dictionary` (Export Metadata (Data Dictionary))|`set_data_dictionary` (Import Metadata (Data Dictionary))|NA|
|`get_instrument_event_mappings` (Export Instrument-Event Mappings)|`set_instrument_event_mappings` (Import Instrument-Event Mappings)|NA|
|`get_records` (Export Records)|`set_records` (Import Records)|`delete_records` (Delete Records)|
|`get_repeating_forms_events` (Export Repeating Instruments and Events)|`set_repeating_forms_events` (Import Repeating Instruments and Events)|NA|
|`get_report_records` (Export Reports)|NA|NA|

### Part 3: Whole project retrieval and structuring

**Functions:**

<table>
<tr>
<th> Name </th> <th> Purpose </th>
</tr>
<tr>
<td>

`get_selector_choice_map`

</td> <td>

Returns a map for every field that needs translation from a numeric index to a
label
value:

```Python
{
  <field_name>: {
    <index>: <value>,
    ...indexes
  },
  ...fields
}
```

</td>
</tr>
<tr>
<td>

`get_records_tree`

</td> <td> Returns all data from the project in the nested form:

```Python
{
  <event>: {                   # event data
    <instrument>: {            # event instrument data
      <record_id>: {           # subject data for this event instrument
        <instance>: {          # subject event instrument instance
          <field>: {<values>}, # set of field values
          ...fields
        },
        ...instances
      },
      ...records
    },
    ...instruments
  },
  ...events
}
```

</td>
</tr>
</table>

There are also some extra utility functions for converting the records tree
into one or more Pandas DataFrames...

<table>
<tr>
<th> Name </th> <th> Purpose </th>
</tr>
<tr>
<td>

`d3b_redcap_api.df_utils.to_df`

</td>
<td>

Converts one `get_records_tree()[event][instrument]` to a pandas DataFrame

</td>
</tr>
<tr>
<td>

`d3b_redcap_api.df_utils.all_dfs`

</td>
<td>

Calls `to_df` on every instrument found in the records tree and returns a dict
keyed by the instrument name if the instrument name is unique or by
event_instrument if not.

</td>
</tr>
</table>

## Example Usage:

```Python
from d3b_redcap_api.redcap import REDCapStudy
from d3b_redcap_api.df_utils import all_dfs

r = REDCapStudy("https://redcap.chop.edu/api/", PROJECT_API_TOKEN)
study_data, errors = r.get_records_tree(raw_selectors=False)

as_dataframes = all_dfs(study_data)
```
