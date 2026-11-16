// Khronos glTF-Validator gegen alle uebergebenen .glb-Dateien. Exit 1 bei Fehlern.
const fs = require('fs');
const validator = require('gltf-validator');
(async () => {
  let bad = 0;
  for (const f of process.argv.slice(2)) {
    const r = await validator.validateBytes(new Uint8Array(fs.readFileSync(f)));
    const i = r.issues;
    console.log(`${f.split('/').pop()}  errors=${i.numErrors} warnings=${i.numWarnings} infos=${i.numInfos}`);
    i.messages.filter(m => m.severity <= 1).forEach(m => console.log(`   ${m.code}: ${m.message} @ ${m.pointer || ''}`));
    if (i.numErrors) bad++;
  }
  process.exit(bad ? 1 : 0);
})();
