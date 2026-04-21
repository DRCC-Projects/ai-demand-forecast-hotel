import requests, time
whitefield_keys = [
    ('g297628-d1776454', 'Lemon Tree Whitefield'),
    ('g297628-d12732541', 'Conrad Bengaluru'),
    ('g297628-d4470098', 'JW Marriott Bengaluru'),
    ('g297628-d1567342', 'ITC Gardenia'),
    ('g297628-d302480', 'The Leela Palace'),
]
from datetime import date, timedelta
cin = date.today().strftime('%Y-%m-%d')
cout = (date.today()+timedelta(1)).strftime('%Y-%m-%d')
print('Checking rates for', cin)
for key, name in whitefield_keys:
    try:
        r = requests.get('https://data.xotelo.com/api/rates',
            params={'hotel_key':key,'chk_in':cin,'chk_out':cout},
            timeout=10)
        data = r.json()
        rates = data.get('result',{}).get('rates',[])
        if rates:
            cheapest = min(x['rate'] for x in rates if x.get('rate'))
            print(name, '| cheapest: INR', cheapest)
        else:
            print(name, '| no rates')
        time.sleep(1)
    except Exception as e:
        print(name, '| error:', e)
