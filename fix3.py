with open('dashboard/app.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace(', unsafe_allow_html=True)', ')', 1)
with open('dashboard/app.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('Done')
