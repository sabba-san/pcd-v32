import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('/home/abbas/development/pcd-v32/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'report_homeowner_profile'")
print("Homeowner Profile Columns:", cur.fetchall())

cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'report_respondent_profile'")
print("Respondent Profile Columns:", cur.fetchall())

cur.close()
conn.close()
