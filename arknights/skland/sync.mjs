// sync.mjs - runs ON THE PC (blender account): read the Arknights account from Skland into the export folder.
//   node sync.mjs   -> D:\Projects\maa-cli\export\skland_info_<stamp>.json (+ skland_info_latest.json)
//                       D:\Projects\maa-cli\export\skland_cultivate_<stamp>.json (+ _latest)
// skland_info: operators with skills / mastery / modules, base layout and levels, stationed operators, etc.
// skland_cultivate: the inventory as Skland reports it. Uses the credentials saved by login.mjs; when they have
// expired, signs in again with the saved Hypergryph OAuth token. Exit 3 = needs a new QR login.
import { createClient } from 'skland-kit'
import fsDriver from 'unstorage/drivers/fs'
import { writeFileSync, mkdirSync, copyFileSync } from 'node:fs'

const STORE = process.env.SKLAND_STORE || 'C:/Users/blender/.skland/store'
const EXPORT = 'D:/Projects/maa-cli/export'
mkdirSync(EXPORT, { recursive: true })
const client = createClient({ driver: fsDriver({ base: STORE }) })
const stamp = new Date().toISOString().slice(0, 16).replace(/[-:]/g, '').replace('T', '-')

async function reauth() {
  const oauth = await client.storage.getItem('hg:oauth')
  if (!oauth) throw Object.assign(new Error('no saved OAuth token'), { relogin: true })
  const { code } = await client.collections.hypergryph.grantAuthorizeCode(oauth)
  await client.signIn(code)
}

async function withAuth(fn) {
  try { return await fn() } catch (e) {
    console.log('retrying after re-auth:', String(e?.message || e).slice(0, 120))
    try { await reauth() } catch (e2) { e2.relogin = true; throw e2 }
    return await fn()
  }
}

function save(kind, data) {
  const p = `${EXPORT}/skland_${kind}_${stamp}.json`
  writeFileSync(p, JSON.stringify({ syncTime: new Date().toISOString(), data }, null, 1))
  copyFileSync(p, `${EXPORT}/skland_${kind}_latest.json`)
  return p
}

try {
  if (!(await client.storage.getItem('skland:cred'))) await reauth()
  try { await client.refresh() } catch { /* refreshed on demand below */ }
  const binding = await withAuth(() => client.collections.player.getBinding())
  const ark = (binding?.list || []).find((g) => g.appCode === 'arknights')
  const role = (ark?.bindingList || []).find((r) => r.isDefault) || ark?.bindingList?.[0]
  if (!role) throw new Error('no Arknights role bound to this Skland account')
  const info = await withAuth(() => client.collections.player.getInfo({ uid: role.uid }))
  const p1 = save('info', info)
  const chars = info?.chars?.length ?? 0
  const rooms = info?.building ? Object.keys(info.building).length : 0
  console.log(`info: ${chars} operators, building sections ${rooms} -> ${p1}`)
  try {
    const cult = await withAuth(() => client.$fetch('/api/v1/game/cultivate/player', { query: { uid: role.uid } }))
    const p2 = save('cultivate', cult?.data ?? cult)
    console.log(`cultivate -> ${p2}`)
  } catch (e) { console.log('cultivate failed:', String(e?.message || e).slice(0, 150)) }
} catch (e) {
  console.log((e.relogin ? 'NEEDS_QR_LOGIN ' : 'FAILED ') + String(e?.message || e).slice(0, 200))
  process.exit(e.relogin ? 3 : 1)
}
