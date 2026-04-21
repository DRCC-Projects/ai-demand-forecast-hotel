import re
with open('dashboard/app.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace("use_container_width=True, config={", "use_container_width=True, config={")
c = c.replace("hovermode='x unified'", "hovermode='x'")
c = re.sub(r"use_container_width=True(?=\s*,\s*hide_index)", "use_container_width=True", c)
with open('dashboard/app.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('Done')
