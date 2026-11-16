import base64, re
S = 'static/'
def b64(p, mime): return 'data:%s;base64,%s' % (mime, base64.b64encode(open(p, 'rb').read()).decode())
def fonts(css):
    return re.sub(r'url\("(?:\.\./)*(?:fonts/)([^"]+)"\)', lambda m: 'url("%s")' % b64(S + 'fonts/' + m.group(1), 'font/woff2'), css)
FF = re.compile(r'@font-face\s*\{[^}]*\}')
tokens_raw = open(S + 'tokens.css', encoding='utf-8').read()
faces = [(re.search(r'font-family:\s*"([^"]+)"', m.group(0)).group(1), re.search(r'url\("fonts/([^"]+)"\)', m.group(0)).group(1), re.search(r'font-weight:\s*(\d+)', m.group(0)).group(1)) for m in FF.finditer(tokens_raw)]
tokens = FF.sub('', tokens_raw)
bundle = FF.sub('', open(S + 'components/bundle.css', encoding='utf-8').read())
# subset the CJK faces to the characters the page uses
import io
from fontTools import subset
from fontTools.ttLib import TTFont
used = set(open('tempauth.js', encoding='utf-8').read() + open(S + 'components/bundle.js', encoding='utf-8').read() + open('index.html', encoding='utf-8').read())
used |= set('0123456789:：/（）()，。、%-—·?？！“”…ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ')
def face_src(fn):
    path = S + 'fonts/' + fn
    if fn.startswith('Sans'):
        f = TTFont(path)
        opts = subset.Options(); opts.flavor = 'woff2'; opts.layout_features = ['*']
        sub = subset.Subsetter(opts); sub.populate(text=''.join(sorted(used))); sub.subset(f)
        buf = io.BytesIO(); f.flavor = 'woff2'; f.save(buf)
        return 'data:font/woff2;base64,' + base64.b64encode(buf.getvalue()).decode()
    return b64(path, 'font/woff2')
fontcss = ''.join('@font-face{font-family:"%s";src:url("%s") format("woff2");font-weight:%s;font-style:normal;font-display:swap}\n' % (fam, face_src(fn), w) for fam, fn, w in faces)
tokens = fontcss + tokens
bundle = re.sub(r'url\(/_blob/([a-f0-9]+)\)', lambda m: 'url("%s")' % b64(S + 'blob/' + m.group(1) + '.png', 'image/png'), bundle)
idx = open('index.html', encoding='utf-8').read()
page_css = re.search(r'<style>(.*?)</style>', idx, re.S).group(1)
new_css = open('tempauth.css', encoding='utf-8').read()
js_bundle = open(S + 'components/bundle.js', encoding='utf-8').read()
app = open('tempauth.js', encoding='utf-8').read()
out = f'''<title>MCP 控制台临时授权</title>
<script>(function(){{var d=document.documentElement,t=null;try{{t=localStorage.getItem('bmcp-theme')}}catch(e){{}}
if(d.dataset.theme!=='light'&&d.dataset.theme!=='dark'){{d.dataset.theme=(t==='light'||t==='dark')?t:(window.matchMedia&&matchMedia('(prefers-color-scheme: light)').matches?'light':'dark')}}}})();</script>
<style>
{tokens}
{bundle}
{page_css}
{new_css}
</style>
<div id="root"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>
<script>
{js_bundle}
</script>
<script>
{app}
</script>
'''
open('tempauth_proto.html', 'w', encoding='utf-8').write(out)
# local preview copy with a doctype and the panel's own React (offline)
loc = out.replace('https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js', 'static/components/lib/react.production.min.js') \
         .replace('https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js', 'static/components/lib/react-dom.production.min.js')
open('preview.html', 'w', encoding='utf-8').write('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + loc + '</body></html>')
import os; print(os.path.getsize('tempauth_proto.html') / 1e6, 'MB')
