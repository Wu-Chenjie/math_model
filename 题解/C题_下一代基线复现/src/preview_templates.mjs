import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
await fs.mkdir('artifacts/previews',{recursive:true});
for(const name of ['result1','result3']){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`inputs/附件/附件5/${name}.xlsx`));
 console.log((await wb.inspect({kind:'sheet',include:'id,name',maxChars:1800})).ndjson);
 for(const s of wb.worksheets.items){
   const range=s.name==='计划购电量'||s.name==='调整购电量'?(name==='result1'?'A1:B8':'A1:G6'):'A1:F8';
   const blob=await wb.render({sheetName:s.name,range,scale:1,format:'png'});
   await fs.writeFile(`artifacts/previews/template-${name}-${s.name}.png`,new Uint8Array(await blob.arrayBuffer()));
 }
}
