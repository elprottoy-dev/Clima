/* Each draft is encrypted independently. No patient metadata is stored in plaintext. */
class DraftVault {
 constructor(storage,cryptoProvider=globalThis.crypto){this.storage=storage;this.crypto=cryptoProvider;this.key=null;this.prefix='clima-v6-draft:';this.metaKey='clima-v6-vault'}
 encode(bytes){return btoa(Array.from(new Uint8Array(bytes),x=>String.fromCharCode(x)).join(''))}
 decode(value){return Uint8Array.from(atob(value),x=>x.charCodeAt(0))}
 async encrypt(value,key=this.key){const iv=this.crypto.getRandomValues(new Uint8Array(12));return {iv:this.encode(iv),data:this.encode(await this.crypto.subtle.encrypt({name:'AES-GCM',iv},key,new TextEncoder().encode(JSON.stringify(value))))}}
 async decrypt(value,key=this.key){return JSON.parse(new TextDecoder().decode(await this.crypto.subtle.decrypt({name:'AES-GCM',iv:this.decode(value.iv)},key,this.decode(value.data))))}
 async unlock(passphrase){
  if(passphrase.length<12)throw Error('Use at least 12 characters');
  let meta=JSON.parse(this.storage.getItem(this.metaKey)||'null');const salt=meta?this.decode(meta.salt):this.crypto.getRandomValues(new Uint8Array(16));
  const base=await this.crypto.subtle.importKey('raw',new TextEncoder().encode(passphrase),'PBKDF2',false,['deriveKey']);
  const key=await this.crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:310000,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
  if(meta){if(await this.decrypt(meta.check,key)!=='CliMa private drafts')throw Error('Incorrect passphrase')}
  else{meta={salt:this.encode(salt),check:await this.encrypt('CliMa private drafts',key)};this.storage.setItem(this.metaKey,JSON.stringify(meta))}
  this.key=key;
 }
 lock(){this.key=null}
 ids(){return Array.from({length:this.storage.length},(_,i)=>this.storage.key(i)).filter(k=>k?.startsWith(this.prefix)).map(k=>k.slice(this.prefix.length))}
 async read(id){if(!this.key)throw Error('Unlock private drafts first');const value=this.storage.getItem(this.prefix+id);if(!value)throw Error('Draft not found');return this.decrypt(JSON.parse(value))}
 async list(){return Promise.all(this.ids().map(async id=>({id,...await this.read(id)})))}
 async put(value,id=this.crypto.randomUUID()){
  if(!this.key)throw Error('Unlock private drafts first');
  if(!/^[a-zA-Z0-9-]{16,80}$/.test(id))throw Error('Invalid draft ID');
  if(!this.storage.getItem(this.prefix+id)&&this.ids().length>=50)throw Error('Maximum 50 saved drafts');
  this.storage.setItem(this.prefix+id,JSON.stringify(await this.encrypt(value)));return id;
 }
 remove(id){this.storage.removeItem(this.prefix+id)}
 async sync(owner,send){
  let sent=0,failed=0;
  for(const entry of await this.list()){
   if(!entry.queued||entry.user?.user?.id!==owner)continue;
   try{await send({...entry.report,client_id:entry.client_id});this.remove(entry.id);sent++}catch(error){failed++}
  }
  return {sent,failed};
 }
}
if(typeof module!=='undefined')module.exports=DraftVault;
