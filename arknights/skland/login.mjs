// login.mjs - runs ON THE PC (blender account): Skland QR login with skland-kit.
//   node login.mjs            -> writes D:\Projects\skland\qr.png, waits up to 3 min for the scan
// The QR image stays on the PC; scan it with the 森空岛 app and confirm. Credentials go to the blender
// account's own folder C:\Users\blender\.skland\store (cred/token from skland-kit, plus the Hypergryph OAuth
// token under "hg:oauth" so sync.mjs can sign in again when the Skland credential expires).
// Progress goes to D:\Projects\skland\login.status; nothing secret is printed.
import { createClient } from 'skland-kit'
import fsDriver from 'unstorage/drivers/fs'
import QRCode from 'qrcode'
import { writeFileSync, mkdirSync, rmSync } from 'node:fs'

const STORE = process.env.SKLAND_STORE || 'C:/Users/blender/.skland/store'
const OUT = 'D:/Projects/skland'
const log = (s) => { writeFileSync(`${OUT}/login.status`, `${new Date().toISOString()} ${s}\n`, { flag: 'a' }); console.log(s) }
mkdirSync(STORE, { recursive: true })
writeFileSync(`${OUT}/login.status`, '')
const client = createClient({ driver: fsDriver({ base: STORE }) })
const hg = client.collections.hypergryph

try {
  const { scanId, scanUrl } = await hg.generateScanLoginUrl()
  await QRCode.toFile(`${OUT}/qr.png`, scanUrl, { width: 480, margin: 2 })
  log('QR_READY D:\\Projects\\skland\\qr.png')
  let scanCode = '', last = ''
  const deadline = Date.now() + 180_000
  while (!scanCode && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 2000))
    try {
      const st = await hg.getScanStatus(scanId)
      if (st.scanCode) scanCode = st.scanCode
    } catch (e) {
      const m = String(e?.message || e).slice(0, 100)
      const state = /101|已扫码|confirm/i.test(m) ? 'SCANNED_WAITING_CONFIRM' : /100|未扫码/.test(m) ? 'WAITING' : 'POLL ' + m
      if (state !== last) { log(state); last = state }
    }
  }
  rmSync(`${OUT}/qr.png`, { force: true })
  if (!scanCode) { log('EXPIRED no scan within 3 min'); process.exit(2) }
  const oauth = await hg.getOAuthTokenByScanCode(scanCode)
  await client.storage.setItem('hg:oauth', oauth)
  const { code } = await hg.grantAuthorizeCode(oauth)
  await client.signIn(code)
  const binding = await client.collections.player.getBinding()
  const ark = (binding?.list || []).find((g) => g.appCode === 'arknights')
  const roles = (ark?.bindingList || []).map((r) => `${r.nickName || r.nickname || '?'}${r.isDefault ? ' (default)' : ''}`)
  log(`LOGGED_IN arknights roles: ${roles.join(', ') || 'none'}`)
} catch (e) {
  rmSync(`${OUT}/qr.png`, { force: true })
  log('FAILED ' + String(e?.message || e).slice(0, 200))
  process.exit(1)
}
