import re
name=None
version=None
editable=False
reqs=[]
with open('uv.lock','r',encoding='utf-8') as f:
    for line in f:
        line=line.strip()
        if line.startswith('[[package]]'):
            if name and version and not editable:
                reqs.append(f"{name}=={version}")
            name=None; version=None; editable=False
        elif line.startswith('name ='):
            m=re.search(r'"([^"]+)"', line)
            if m: name=m.group(1)
        elif line.startswith('version ='):
            m=re.search(r'"([^"]+)"', line)
            if m: version=m.group(1)
        elif 'editable' in line:
            editable=True
if name and version and not editable:
    reqs.append(f"{name}=={version}")
with open('requirements-uv.txt','w',encoding='utf-8') as out:
    out.write('\n'.join(reqs))
print('wrote requirements-uv.txt with', len(reqs), 'entries')
