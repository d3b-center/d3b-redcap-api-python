<p align="center">
  <img alt="Logo for The Center for Data Driven Discovery" src="docs/_media/logo.svg" width="400px" />
</p>
<p align="center">
  <a href="https://github.com/d3b-center/d3b-redcap-api-python/blob/master/LICENSE"><img src="https://img.shields.io/github/license/d3b-center/d3b-redcap-api-python.svg?style=for-the-badge"></a>
  <a href="https://circleci.com/gh/d3b-center/d3b-redcap-api-python"><img src="https://img.shields.io/circleci/project/github/d3b-center/d3b-redcap-api-python.svg?style=for-the-badge"></a>
  <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black ----line--length 80-000000.svg?style=for-the-badge"></a>
</p>

# REDCap API in Python

Supports structured data extraction for REDCap projects

```Python
from d3b_redcap_api.redcap import REDCapStudy


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
r = REDCapStudy("https://redcap.chop.edu/api/", PROJECT_API_TOKEN)
study_data, errors = r.get_records_tree(raw_selectors=False)
```
