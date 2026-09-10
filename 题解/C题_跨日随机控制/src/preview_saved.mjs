import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const file=process.argv[2];
if(!/^result(?:1|2|3|4-2|4-3)$/.test(file)) throw Error('Specify one output workbook');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`计算结果/${file}.xlsx`));
for(const s of wb.worksheets.items){
 const range=s.name==='口径说明'?'A1:B15':s.name==='计划购电量'&&file==='result1'?'A1:B8':s.name==='紧急购电量'?'A1:C8':s.name==='费用汇总'?'A1:J8':'A1:F8';
 const blob=await wb.render({sheetName:s.name,range,scale:1.3,format:'png'});
 await fs.writeFile(`artifacts/previews/${file}-${s.name}.png`,new Uint8Array(await blob.arrayBuffer()));
}
