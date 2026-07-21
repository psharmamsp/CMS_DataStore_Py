import requests
url = "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items"

response = requests.get(url, timeout=30)
response.raise_for_status()

datasets= response.jason()

hospital_datasets = [
   ds for ds in datasets
   if "Hospitals" in ds.get("theme",[])
]

##Read CSV

import pandas as pd

df = pd.read_csv(Csv_file)
