# local_unpaywall
Mirroring open access urls for scientific publications on a local postgress server

Step 0: Create the necessary tables in yor postgres database:


Step 1: Sync the baseline snapshot from OpenAlex - we only need the "works" sction, which more than halves the massive download (still some 150GB):
```shell
aws s3 sync "s3://openalex/data/works" "openalex-snapshot/data/works" --no-sign-request
```

Step 2: extract the data we need and flatten it into csv. Keep that file, because later synchronisations and extractions will still need it

Step 3: import the data into your postgres database

Step 4: if you need to, you can now bulk download open access full text papers 
