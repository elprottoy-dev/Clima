"""Read-only production configuration checks. Never prints secret values."""
import os,json,sys,importlib.util
from urllib.parse import urlparse
from pathlib import Path

def checks():
 origin=os.getenv('CLIMA_ORIGIN','');u=urlparse(origin)
 result={'https_origin':u.scheme=='https' and bool(u.hostname) and not u.username and not u.password and not u.query and not u.fragment and u.path in ('','/'),
 'admin_password':len(os.getenv('CLIMA_ADMIN_PASSWORD',''))>=12,
 'staff_mfa_required':os.getenv('CLIMA_REQUIRE_STAFF_MFA','1')=='1',
 'persistent_database':bool(os.getenv('CLIMA_DB') or os.getenv('CLIMA_DATABASE_URL')),
 'firebase_project':bool(os.getenv('FIREBASE_PROJECT_ID')),
 'firebase_credentials_file':bool(os.getenv('FIREBASE_CREDENTIALS_JSON')) or Path(os.getenv('GOOGLE_APPLICATION_CREDENTIALS','/nonexistent')).is_file(),
 'smtp_host_and_sender':bool((os.getenv('CLIMA_SMTP_HOST') or os.getenv('BREVO_API_KEY')) and os.getenv('CLIMA_SMTP_FROM')),
 'android_firebase_config':(Path(__file__).parent/'android/app/google-services.json').is_file(),
 'android_signing_file':Path(os.getenv('CLIMA_KEYSTORE','/nonexistent')).is_file(),
 'android_signing_settings':all(os.getenv(k) for k in ['CLIMA_KEYSTORE_PASSWORD','CLIMA_KEY_ALIAS','CLIMA_KEY_PASSWORD'])}
 try:
  from cryptography.fernet import Fernet
  Fernet(os.getenv('CLIMA_DATA_KEY','').encode());result['persistent_data_key']=True
 except (ValueError,ImportError):result['persistent_data_key']=False
 for name in ['waitress','PIL','pymupdf','requests']:result['dependency_'+name]=importlib.util.find_spec(name) is not None
 return result
if __name__=='__main__':
 result=checks()
 print(json.dumps({'checks':result,'ready_for_external_validation':all(result.values()),'note':'Passing checks does not verify DNS, HTTPS, provider delivery, disk encryption, clinical approval or physical-device behavior.'},indent=2))
 sys.exit(0 if all(result.values()) else 1)
