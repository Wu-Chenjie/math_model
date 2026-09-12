import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const pairs=[['result1',null],['result2','q2'],['result3','q3'],['result4-2','q4_2'],['result4-3','q4_3']];
const date=s=>new Date(`${s}T00:00:00Z`);
const preview=async(wb,file,phase)=>{
 for(const s of wb.worksheets.items){
  const range=s.name==='口径说明'?'A1:B7':file==='result1'?(s.name==='充放电量'?'A1:E7':'A1:B8'):s.name==='充放电量'?'A1994:F2005':s.name==='费用汇总'?'A331:J336':s.name==='紧急购电量'?'A1:C7':'A331:F335';
  const b=await wb.render({sheetName:s.name,range,scale:1.1,format:'png'});
  await fs.writeFile(`artifacts/previews/${phase}-${file}-${s.name}.png`,new Uint8Array(await b.arrayBuffer()));
 }
};
await fs.mkdir('artifacts/previews',{recursive:true});
const payload=JSON.parse(await fs.readFile('artifacts/workbook-payload.json','utf8'));
for(const [file,key] of pairs){
 if(process.argv[3] && process.argv[3]!==file)continue;
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`../计算结果/${file}.xlsx`));
 if(process.argv[2]==='inspect'){await preview(wb,file,'before');continue;}
 if(!key){
  wb.worksheets.getItem('口径说明').getRange('A1').write(payload.notes);
  console.log(file,(await wb.inspect({kind:'table',range:'计划购电量!A146:B147',include:'values,formulas',maxChars:700})).ndjson);
  console.log(file,(await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1000})).ndjson);
  await (await SpreadsheetFile.exportXlsx(wb)).save(`计算结果/${file}.xlsx`);await preview(wb,file,'after');continue;
 }
 const m=payload.models[key];
 for(const name of ['计划购电量',...(key.endsWith('3')?['调整购电量']:[])]){
  const s=wb.worksheets.getItem(name),isPlan=name==='计划购电量';
  s.getRange('B334:EO335').values=(isPlan?m.q:m.r).slice(-2);
  s.getRange('EQ334:EQ335').values=m.daily.slice(-2).map(r=>[r.planned_cost+(isPlan?0:r.increase_cost+r.reduction_net_cost)]);
 }
 const bs=wb.worksheets.getItem('充放电量');
 bs.getRange('A1994:F2005').values=m.battery.slice(-12).map((r,i)=>[i%6===0?date(r[0]):null,...r.slice(1)]);
 const es=wb.worksheets.getItem('紧急购电量');es.getUsedRange().clear({applyTo:'contents'});
 es.getRange('A1:C1').values=[['日期','购电时间段','购电量']];
 es.getRange('A2').write(m.emergency.map(r=>[date(r[0]),...r.slice(1)]));
 es.getRange(`A2:A${m.emergency.length+1}`).setNumberFormat('yyyy-mm-dd');es.getRange(`C2:C${m.emergency.length+1}`).setNumberFormat('0.0000');
 const cs=wb.worksheets.getItem('费用汇总'),fields=['planned_cost','increase_cost','reduction_net_cost','emergency_cost','total_cost','planned_energy','adjusted_energy','emergency_energy','spill_energy'];
 cs.getRange('B334:J335').values=m.daily.slice(-2).map(r=>fields.map(f=>r[f]));
 const ns=wb.worksheets.getItem('口径说明');ns.getRange('A1').write(payload.notes);
 console.log(file,(await wb.inspect({kind:'table',range:'费用汇总!A334:F336',include:'values,formulas',tableMaxRows:3,tableMaxCols:6,maxChars:1600})).ndjson);
 console.log(file,(await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1000})).ndjson);
 await (await SpreadsheetFile.exportXlsx(wb)).save(`计算结果/${file}.xlsx`);
 await preview(wb,file,'after');
}
