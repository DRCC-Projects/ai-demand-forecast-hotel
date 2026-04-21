f=open('dashboard/app.py','r',encoding='utf-8')
c=f.read()
f.close()
c=c.replace('st.markdown', 'st.html', 1)
idx=c.find('unsafe_allow_html=True)')
if idx != -1:
    c=c[:idx] + c[idx+len('unsafe_allow_html=True)'):]
f=open('dashboard/app.py','w',encoding='utf-8')
f.write(c)
f.close()
print('Fixed')
