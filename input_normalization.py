"""Canonical digits in user answers; never rewrite authentication secrets."""
DIGITS=str.maketrans('০১২৩৪৫৬৭৮৯','0123456789')
OPAQUE={'password','password_confirm','old_password','new_password','current_password','token','secret','recovery_code','code','credential','subscription','endpoint','keys','p256dh','auth','file','data','content','base64','attachment'}
def normalize_answers(value,key=''):
 if key.lower() in OPAQUE or any(x in key.lower() for x in ('password','token','secret','base64')):return value
 if isinstance(value,str):return value.translate(DIGITS)
 if isinstance(value,list):return [normalize_answers(v,key) for v in value]
 if isinstance(value,dict):return {k:normalize_answers(v,k) for k,v in value.items()}
 return value
