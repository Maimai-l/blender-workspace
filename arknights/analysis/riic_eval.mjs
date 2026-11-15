// riic_eval.mjs - RIIC's infrastructure evaluator, run locally from the public RIIC-Web repository
// (apps/arknights/public/wasm/, PolyForm Noncommercial 1.0.0; personal use).
//   node riic_eval.mjs <RIIC-Web dir> < request.json > response.json
// Request/response: NativeEvalRequestV1 / NativeEvalResponseV1 (apps/arknights/src/lib/infra-eval/client.ts).
// The request may also be a JSON array of requests; the output is then an array of responses.
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { join } from 'node:path'

const dir = join(process.argv[2] || '.', 'apps/arknights/public/wasm')
const manifest = JSON.parse(readFileSync(join(dir, 'infra-eval-manifest.json'), 'utf8'))
const glue = await import(pathToFileURL(join(dir, manifest.glueUrl.split('/').pop())).href)
glue.initSync({ module: readFileSync(join(dir, manifest.wasmUrl.split('/').pop())) })
const input = JSON.parse(readFileSync(0, 'utf8'))
const one = (req) => JSON.parse(glue.evaluate_v1(JSON.stringify(req)))
process.stdout.write(JSON.stringify(Array.isArray(input) ? input.map(one) : one(input)))
