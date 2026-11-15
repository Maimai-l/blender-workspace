import json
d = json.load(open("D:\\Projects\\maa-cli\\state\\copilot_match.json", encoding="utf-8"))
for st, L in d.items():
    L = sorted(L, key=lambda o: (len(o['missing']), -(o['rating'] if not o['few_ratings'] else 5), -o['views']))
    print('=====', st)
    for o in L[:4]:
        print(f" {o['id']} d{o['difficulty']} r{o['rating']}{'?' if o['few_ratings'] else ''} v{o['views']} {o['upload']} {o['title'][:34]} | {' '.join(o['opers'])} {o['groups']}")
        for m in o['missing']:
            print('    缺:', m['name'], m['why'])
