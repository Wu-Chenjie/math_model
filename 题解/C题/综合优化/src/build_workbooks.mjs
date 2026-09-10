import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const payload=JSON.parse(await fs.readFile('artifacts/workbook-payload.json','utf8'));
const out='计算结果';await fs.mkdir(out,{recursive:true});
const pairs=[['result1',null],['result2','q2'],['result3','q3'],['result4-2','q4_2'],['result4-3','q4_3']];
const dateValue=s=>new Date(`${s}T00:00:00Z`);
const style=(s,rows,cols)=>{
 const r=s.getRangeByIndexes(0,0,rows,cols);r.format.font={name:'Arial',size:11};r.format.rowHeight=20;
 s.getRangeByIndexes(0,0,1,cols).format.font={bold:true};
 s.getRangeByIndexes(0,0,rows,1).format.columnWidth=16;
 s.getRangeByIndexes(0,1,rows,Math.max(1,cols-1)).format.columnWidth=19;
};
for(const [file,key] of pairs){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`inputs/附件/附件5/${file}.xlsx`));
 const qsheet=wb.worksheets.getItem('计划购电量');
 if(!key){
  const q=payload.q1;
  qsheet.getRange('A2:B145').values=payload.labels.map((v,i)=>[v,q.q[i]]);
  qsheet.getRange('A146:B147').values=[['全天购电量',null],['全天购电费',q.daily_cost]];
  qsheet.getRange('B146').formulas=[['=SUM(B2:B145)']];qsheet.getRange('B2:B147').setNumberFormat('0.0000');
  style(qsheet,147,2);qsheet.getRange('A1:A147').format.columnWidth=22;
  const s=wb.worksheets.getItem('充放电量');
  s.getRange('B2:C7').values=Array.from({length:6},(_,b)=>[q.c.slice(b*24,b*24+24).reduce((a,v)=>a+v,0),q.d.slice(b*24,b*24+24).reduce((a,v)=>a+v,0)]);
  s.getRange('E2:E3').values=[[q.state[0]],[q.state[144]]];s.getRange('B2:C7').setNumberFormat('0.0000');
  style(s,7,5);
 }else{
  const m=payload.models[key];
  for(const name of ['计划购电量',...(key.endsWith('3')?['调整购电量']:[])]){
   const s=wb.worksheets.getItem(name);const isPlan=name==='计划购电量';
   s.getRange('B1:EO1').values=[payload.labels];
   s.getRange('B2:EO335').values=isPlan?m.q:m.r;
   s.getRange('A2:A335').values=m.dates.map(d=>[dateValue(d)]);s.getRange('A2:A335').setNumberFormat('yyyy-mm-dd');
   s.getRange('EP2').formulas=[['=SUM(B2:EO2)']];s.getRange('EP2:EP335').fillDown();
   s.getRange('EQ2:EQ335').values=m.daily.map(r=>[r.planned_cost+(isPlan?0:r.increase_cost+r.reduction_net_cost)]);
   s.getRange('B2:EQ335').setNumberFormat('0.0000');style(s,335,147);
   s.freezePanes.freezeRows(1);s.freezePanes.freezeColumns(1);
  }
  const bs=wb.worksheets.getItem('充放电量');bs.getUsedRange().clear({applyTo:'contents'});
  bs.getRange('A1:F1').values=[['日期','时间段','充电量','放电量','时刻','储电量']];
  bs.getRange('A2').write(m.battery.map((r,i)=>[i%6===0?dateValue(r[0]):null,...r.slice(1)]));
  bs.getRange(`A2:A${m.battery.length+1}`).setNumberFormat('yyyy-mm-dd');
  bs.getRange(`C2:D${m.battery.length+1}`).setNumberFormat('0.0000');
  bs.getRange(`F2:F${m.battery.length+1}`).setNumberFormat('0.0000');style(bs,m.battery.length+1,6);
  const es=wb.worksheets.getItem('紧急购电量');es.getUsedRange().clear({applyTo:'contents'});
  es.getRange('A1:C1').values=[['日期','购电时间段','购电量']];
  es.getRange('A2').write(m.emergency.map(r=>[dateValue(r[0]),...r.slice(1)]));
  es.getRange(`A2:A${m.emergency.length+1}`).setNumberFormat('yyyy-mm-dd');es.getRange(`C2:C${m.emergency.length+1}`).setNumberFormat('0.0000');
  style(es,m.emergency.length+1,3);es.getRange(`B1:B${m.emergency.length+1}`).format.columnWidth=24;
  const cs=wb.worksheets.add('费用汇总');const fields=['planned_cost','increase_cost','reduction_net_cost','emergency_cost','total_cost','planned_energy','adjusted_energy','emergency_energy','spill_energy'];
  cs.getRange('A1:J1').values=[['日期','计划费用_元','增购费用_元','退购净费用_元','紧急费用_元','总费用_元','计划电量_kWh','最终合同电量_kWh','紧急电量_kWh','弃电量_kWh']];
  cs.getRange('A2').write(m.daily.map(r=>[dateValue(r.date),...fields.map(f=>r[f])]));
  cs.getRange('A2:A335').setNumberFormat('yyyy-mm-dd');cs.getRange('B2:J336').setNumberFormat('0.0000');
  cs.getRange('A336').values=[['合计']];
  for(let j=1;j<10;j++){const col=String.fromCharCode(65+j);cs.getCell(335,j).formulas=[[`=SUM(${col}2:${col}335)`]];}
  style(cs,336,10);cs.getRange('B1:J1').format.wrapText=true;cs.getRange('A1:J1').format.rowHeight=32;
 }
 const ns=wb.worksheets.add('口径说明');ns.getRange('A1').write(payload.notes);style(ns,payload.notes.length,2);
 ns.getRange(`B1:B${payload.notes.length}`).format.columnWidth=115;ns.getRange(`A1:B${payload.notes.length}`).format.wrapText=true;
 ns.getRange(`A1:B${payload.notes.length}`).format.rowHeight=36;
 const err=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1500});
 console.log(file,'error_scan',err.ndjson);
 console.log((await wb.inspect({kind:'table',range:'计划购电量!A1:D4',include:'values,formulas',tableMaxRows:4,tableMaxCols:4,maxChars:1200})).ndjson);
 for(const s of wb.worksheets.items){
  const range=s.name==='口径说明'?'A1:B6':s.name==='计划购电量'&& !key?'A1:B8':s.name==='紧急购电量'?'A1:C8':'A1:F8';
  const blob=await wb.render({sheetName:s.name,range,scale:1.3,format:'png'});
  await fs.writeFile(`artifacts/previews/${file}-${s.name}.png`,new Uint8Array(await blob.arrayBuffer()));
 }
 await (await SpreadsheetFile.exportXlsx(wb)).save(`${out}/${file}.xlsx`);
 await fs.rm(`${out}/${file}.xlsx.inspect.ndjson`,{force:true});
 console.log('EXPORTED',file);
}
