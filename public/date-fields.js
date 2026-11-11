/* Explicit day/month/year entry, independent of Android or browser locale. */
(()=>{
 const ascii=s=>String(s).replace(/[০-৯]/g,c=>String(c.charCodeAt(0)-0x09e6));
 function mount(input){
  if(input.dataset.dateParts)return;
  input.dataset.dateParts='1';
  const time=input.type==='datetime-local',required=input.required;
  const descriptor=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
  const initial=input.value;
  input.type='hidden';input.required=false;
  const box=document.createElement('span');box.className='date-parts';
  const parts=[['দিন','DD',2],['মাস','MM',2],['সাল','YYYY',4]].map(([title,placeholder,length])=>{
   const cell=document.createElement('span'),caption=document.createElement('span'),field=document.createElement('input');
   caption.textContent=title;field.type='text';field.inputMode='numeric';field.placeholder=placeholder;field.maxLength=length;field.pattern=`[0-9]{${length===4?'4':'1,2'}}`;field.required=required;field.setAttribute('aria-label',title);field.autocomplete='off';
   cell.append(caption,field);box.append(cell);return field;
  });
  let clock;
  if(time){clock=document.createElement('input');clock.type='time';clock.required=required;clock.setAttribute('aria-label','সময়');box.append(clock)}
  input.after(box);
  function paint(v){const match=/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?/.exec(v);parts.forEach((x,i)=>x.value=match?match[3-i]:'');if(clock)clock.value=match?.[4]||'';parts.forEach(x=>x.setCustomValidity(''))}
  Object.defineProperty(input,'value',{configurable:true,get(){return descriptor.get.call(input)},set(v){descriptor.set.call(input,v);paint(String(v))}});
  function sync(){
   parts.forEach(x=>{x.value=ascii(x.value);x.setCustomValidity('')});
   const [d,m,y]=parts.map(x=>x.value),any=parts.some(x=>x.value)||(clock?.value);
   const value=`${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;
   const check=new Date(Date.UTC(Number(y),Number(m)-1,Number(d)));
   let error='';
   if(any&&(!d||!m||y.length!==4||Number(y)<1000||check.getUTCFullYear()!==Number(y)||check.getUTCMonth()+1!==Number(m)||check.getUTCDate()!==Number(d)))error='দিন, মাস ও চার অঙ্কের সাল দিয়ে সঠিক তারিখ লিখুন';
   let result=any&&!error?value+(clock?'T'+clock.value:''):'';
   if(result&&((input.min&&result<input.min)||(input.max&&result>input.max)))error='অনুমোদিত সময়সীমার মধ্যে তারিখ দিন';
   if(clock&&any&&!clock.value)error='সময় নির্বাচন করুন';
   parts[0].setCustomValidity(error);descriptor.set.call(input,error?'':result);
   input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
  }
  [...parts,...(clock?[clock]:[])].forEach(x=>x.addEventListener('input',sync));
  paint(initial);
  if(input.form)input.form.addEventListener('reset',()=>queueMicrotask(()=>paint(input.defaultValue)));
 }
 function scan(){document.querySelectorAll('input[type="date"],input[type="datetime-local"]').forEach(mount)}
 new MutationObserver(scan).observe(document.documentElement,{childList:true,subtree:true});scan();
})();
