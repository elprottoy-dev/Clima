"""Validated onboarding; private answers are encrypted as one versioned payload."""
import datetime,json,re
from pathlib import Path
import clinical
LOCATIONS=json.loads((Path(__file__).parent/'public/locations.json').read_text())
OCCUPATIONS=['গৃহস্থালি ও পরিবারের যত্ন','শিক্ষার্থী','কৃষিকাজ','মৎস্যচাষ / মাছ ধরা','পশুপালন / হাঁস-মুরগি পালন','দিনমজুরি','নির্মাণশ্রমিক','গার্মেন্টস / কারখানার কাজ','গৃহকর্মী','ক্ষুদ্র ব্যবসা / দোকান','উদ্যোক্তা / ব্যবসায়ী','সরকারি চাকরি','বেসরকারি চাকরি','এনজিও / উন্নয়নকর্মী','শিক্ষক','চিকিৎসক','নার্স / স্বাস্থ্যকর্মী','প্রকৌশলী / তথ্যপ্রযুক্তি','আইনজীবী','চালক / পরিবহনকর্মী','সেলাই / হস্তশিল্প','বিক্রয় / সেবাকর্মী','ফ্রিল্যান্সিং / অনলাইন কাজ','প্রবাসী কর্মী','অবসরপ্রাপ্ত','বর্তমানে কর্মহীন','অসুস্থতা / প্রতিবন্ধিতার কারণে কাজ করেন না','অন্যান্য']
def init(c):c.execute('CREATE TABLE IF NOT EXISTS registration_profiles(uid INTEGER PRIMARY KEY,payload TEXT NOT NULL)')
def text(d,k,required=True):
 v=d.get(k,'')
 if not isinstance(v,str) or len(v)>300 or (required and not v.strip()):raise ValueError('প্রয়োজনীয় তথ্য সঠিকভাবে পূরণ করুন: '+k)
 return v.strip()
def date(v):
 try:return datetime.date.fromisoformat(v)
 except (ValueError,TypeError):raise ValueError('সঠিক তারিখ নির্বাচন করুন')
def validate(d):
 name=text(d,'name_bn');phone=text(d,'phone').translate(str.maketrans('০১২৩৪৫৬৭৮৯','0123456789')).replace(' ','').replace('-','')
 if phone.startswith('+88'):phone=phone[3:]
 if not re.fullmatch(r'01[3-9][0-9]{8}',phone):raise ValueError('১১ সংখ্যার বাংলাদেশি মোবাইল নম্বর দিন')
 if not re.search('[\u0980-\u09ff]',name) or len(name)>100:raise ValueError('বাংলায় নাম লিখুন')
 today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=6))).date();birth=date(d.get('birth_date'));age=today.year-birth.year-((today.month,today.day)<(birth.month,birth.day))
 if not 1<=age<=120 or birth>today:raise ValueError('জন্মতারিখ সঠিক নয়')
 state=d.get('marital_status')
 if state not in ['unmarried','married']:raise ValueError('বৈবাহিক অবস্থা নির্বাচন করুন')
 p={'version':1,'name_bn':name,'phone':phone,'birth_date':birth.isoformat(),'age_at_registration':age,'marital_status':state}
 for k in ['division','district','upazila','area_type','local_area','village','occupation']:p[k]=text(d,k)
 division=next((x for x in LOCATIONS if x['bn_name']==p['division']),None)
 district=next((x for x in (division or {}).get('districts',[]) if x['name']==p['district']),None)
 upazila=next((x for x in (district or {}).get('upazilas',[]) if x['bn_name']==p['upazila']),None)
 if not upazila:raise ValueError('বিভাগ, জেলা ও উপজেলা মিলিয়ে নির্বাচন করুন')
 if p['area_type'] not in ['union','municipality','city']:raise ValueError('এলাকার ধরন নির্বাচন করুন')
 if p['area_type']=='union' and p['local_area'] not in [x['bn_name'] for x in upazila.get('unions',[])]:raise ValueError('তালিকা থেকে ইউনিয়ন নির্বাচন করুন')
 p['ward']=text(d,'ward',False);p['district_bn']=district['bn_name']
 if p['occupation'] not in OCCUPATIONS:raise ValueError('পেশা নির্বাচন করুন')
 p['occupation_other']=text(d,'occupation_other',p['occupation']=='অন্যান্য') if p['occupation']=='অন্যান্য' else ''
 if state=='married':
  try:ma=int(str(d.get('marriage_age','')).translate(str.maketrans('০১২৩৪৫৬৭৮৯','0123456789')));children=int(str(d.get('children','')).translate(str.maketrans('০১২৩৪৫৬৭৮৯','0123456789')))
  except ValueError:raise ValueError('বিয়ের বয়স ও সন্তানের সংখ্যা লিখুন')
  if not 1<=ma<=age or not 0<=children<=30:raise ValueError('বিয়ের বয়স বা সন্তানের সংখ্যা সঠিক নয়')
  p.update(marriage_age=ma,children=children)
  md=text(d,'marriage_date',False)
  if md:
   wedding=date(md);wa=wedding.year-birth.year-((wedding.month,wedding.day)<(birth.month,birth.day))
   if wedding<birth or wedding>today or wa!=ma:raise ValueError('বিয়ের তারিখ ও বিয়ের বয়স মিলছে না')
  p['marriage_date']=md
  for k in ['pregnant','husband_earns']:
   if d.get(k) not in ['yes','no']:raise ValueError('হ্যাঁ অথবা না নির্বাচন করুন')
   p[k]=d[k]
  p['husband_no_income_reason']=text(d,'husband_no_income_reason') if p['husband_earns']=='no' else ''
  p['husband_occupation']=text(d,'husband_occupation')
  if p['husband_occupation'] not in OCCUPATIONS:raise ValueError('স্বামীর পেশা নির্বাচন করুন')
  p['husband_occupation_other']=text(d,'husband_occupation_other') if p['husband_occupation']=='অন্যান্য' else ''
  p['income_source']=text(d,'income_source')
 if d.get('profile_consent') not in [True,'on']:raise ValueError('তথ্য সংরক্ষণের সম্মতি প্রয়োজন')
 p['consented_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 return p,age,phone
LABELS={'phone':'ফোন নম্বর','birth_date':'জন্মতারিখ','marital_status':'বৈবাহিক অবস্থা','occupation':'নিজের পেশা','occupation_other':'নিজের অন্যান্য পেশা','division':'বিভাগ','district_bn':'জেলা','upazila':'উপজেলা','area_type':'এলাকার ধরন','local_area':'ইউনিয়ন / পৌরসভা / সিটি করপোরেশন','ward':'ওয়ার্ড','village':'গ্রাম / মহল্লা','marriage_age':'বিয়ের সময় বয়স','marriage_date':'বিয়ের তারিখ','pregnant':'বর্তমানে গর্ভবতী','children':'সন্তানের সংখ্যা','husband_earns':'স্বামী আয় করেন','husband_no_income_reason':'স্বামী আয় না করার কারণ','husband_occupation':'স্বামীর পেশা','husband_occupation_other':'স্বামীর অন্যান্য পেশা','income_source':'আয়ের উৎস','consented_at':'সম্মতির সময়'}
def export(c,uid):
 r=c.execute('SELECT payload FROM registration_profiles WHERE uid=?',(uid,)).fetchone()
 if not r:return {}
 p=clinical.unpack(r['payload']);values={'yes':'হ্যাঁ','no':'না','married':'বিবাহিত','unmarried':'অবিবাহিত','union':'ইউনিয়ন','municipality':'পৌরসভা','city':'সিটি করপোরেশন'}
 return {label:values.get(p.get(k,''),p.get(k,'')) for k,label in LABELS.items()}
