# REDCap API in Python

Supports structured data extraction for REDCap projects

```Python
from redcap import REDCapStudy


r = REDCapStudy("https://redcap.chop.edu/api/", PROJECT_API_TOKEN)
study_data = r.get_records_tree()
```
