import runpy
print("start", flush=True)
runpy.run_path("scripts/cutover_dump_cloud_sql.py", run_name="__main__")
