"""Print schema, row counts, null rates and sample rows of each real parquet file."""
import glob, os, sys
import pandas as pd
import pyarrow.parquet as pq

root = os.path.join(os.path.dirname(__file__), "..")
out = open(os.path.join(root, "outputs", "schema_report.txt"), "w")
def P(*a):
    print(*a); print(*a, file=out)
for f in sorted(glob.glob(os.path.join(root, "data/raw/*.parquet"))):
    pf = pq.ParquetFile(f)
    P("=" * 80); P(os.path.basename(f), "rows:", pf.metadata.num_rows)
    P(pf.schema_arrow)
    df = pf.read_row_group(0).to_pandas().head(200)
    P(df.head(5).T.to_string())
    P("null rate (first 200 rows):"); P(df.isna().mean().round(3).to_string())
