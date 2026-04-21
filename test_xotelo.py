import requests
r = requests.get('https://data.xotelo.com/api/list',
    params={'location_key':'g297628','offset':0,'limit':30},
    timeout=15)
print('Status:', r.status_code)
data = r.json()
if data.get('result') and data['result'].get('list'):
    hotels = data['result']['list']
    print('Found', len(hotels), 'hotels')
    for h in hotels[:15]:
        print(' ', h['key'], '|', h['name'])
else:
    print('No hotels:', data)
