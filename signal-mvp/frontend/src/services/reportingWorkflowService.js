const CASES_KEY='signalAdminCases'
const BATCHES_KEY='signalBatches'
const read=(key,fallback)=>{try{return JSON.parse(localStorage.getItem(key)||'null')??fallback}catch{return fallback}}
const write=(key,value)=>localStorage.setItem(key,JSON.stringify(value))
export const reportingWorkflowService={
  getCaseStates:()=>read(CASES_KEY,{}),
  setCaseState:(id,patch)=>{const all=read(CASES_KEY,{});all[id]={...(all[id]||{}),...patch};write(CASES_KEY,all);return all[id]},
  getBatches:()=>read(BATCHES_KEY,[]),
  submitBatch:(ids,phaByCase={})=>{const cases=read(CASES_KEY,{});const eligible=ids.filter(id=>cases[id]?.adminVerificationStatus==='Verified');if(!eligible.length)return null;const batches=read(BATCHES_KEY,[]);const sequence=batches.length+1;const batchId=`BATCH-${String(sequence).padStart(3,'0')}`;const submittedAt=new Date().toLocaleString();const destinations=[...new Set(eligible.map(id=>phaByCase[id]).filter(Boolean))];const pha=destinations.length===1?destinations[0]:destinations.length>1?'Multiple PHA destinations (demo)':'Configured PHA destination (demo)';const batch={id:batchId,ids:eligible,submittedAt,pha,acknowledgement:'Awaiting Acknowledgement',status:'Submitted'};batches.push(batch);write(BATCHES_KEY,batches);eligible.forEach(id=>cases[id]={...cases[id],submissionStatus:'Submitted',status:'Submitted',batchId,submittedAt,pha:phaByCase[id]||pha,acknowledgement:batch.acknowledgement});write(CASES_KEY,cases);return batch},
  acknowledgeCase:(id)=>{const cases=read(CASES_KEY,{});if(!cases[id])return cases;cases[id]={...cases[id],submissionStatus:'Acknowledged',status:'Acknowledged',acknowledgement:'Acknowledged'};write(CASES_KEY,cases);const batches=read(BATCHES_KEY,[]);const batch=batches.find(item=>item.id===cases[id].batchId);if(batch&&batch.ids.every(caseId=>cases[caseId]?.submissionStatus==='Acknowledged')){batch.acknowledgement='Acknowledged';write(BATCHES_KEY,batches)}return cases},
}
