import requests
from datetime import date, timedelta
cin = date.today().strftime('%Y-%m-%d')
cout = (date.today()+timedelta(1)).strftime('%Y-%m-%d')
r = requests.get('https://data.xotelo.com/api/rates',
    params={'hotel_key':'g297628-d12732541',
            'chk_in':cin,'chk_out':cout,
            'currency':'INR'},
    timeout=10)
data = r.json()
rates = data.get('result',{}).get('rates',[])
print('Currency test:')
for rate in rates[:5]:
    print(' ', rate.get('name'), rate.get('rate'))
