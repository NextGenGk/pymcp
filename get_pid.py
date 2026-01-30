from server import supabase
import json

response = supabase.table("patients").select("pid").limit(1).execute()
if response.data:
    print(response.data[0]['pid'])
else:
    print("No patients found")
