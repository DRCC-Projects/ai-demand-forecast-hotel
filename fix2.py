with open('dashboard/app.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Find st.html(\"\"\" and ensure it closes properly
# The issue is the ) was removed - add it back
c = c.replace('st.html(\"\"\"', 'st.html(\"\"\"', 1)

# Find the end of the CSS block - after </style> tag
import re
# Replace the broken st.html block - find it and fix closing
lines = c.split('\n')
new_lines = []
in_html = False
fixed = False
for i, line in enumerate(lines):
    if 'st.html(\"\"\"' in line and not fixed:
        in_html = True
    if in_html and '</style>' in line and not fixed:
        new_lines.append(line)
        # Check if next line closes properly
        if i+1 < len(lines) and '\"\"\"' not in lines[i+1]:
            new_lines.append('\"\"\")')
            in_html = False
            fixed = True
            continue
    new_lines.append(line)

c = '\n'.join(new_lines)
with open('dashboard/app.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('Fixed closing paren')
