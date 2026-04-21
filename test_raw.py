import requests
from datetime import date, timedelta
import json
cin = date.today().strftime('%Y-%m-%d')
cout = (date.today()+timedelta(1)).strftime('%Y-%m-%d')
r = requests.get('https://data.xotelo.com/api/rates',
    params={'hotel_key':'g297628-d12732541',
            'chk_in':cin,'chk_out':cout,'currency':'INR'},
    timeout=15)
print('Status:', r.status_code)
print(json.dumps(r.json(), indent=2)[:800])
