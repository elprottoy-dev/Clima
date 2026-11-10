"""Versioned, validated seasonal observations stored inside encrypted case payloads."""
MONTHS=['বৈশাখ','জ্যৈষ্ঠ','আষাঢ়','শ্রাবণ','ভাদ্র','আশ্বিন','কার্তিক','অগ্রহায়ণ','পৌষ','মাঘ','ফাল্গুন','চৈত্র']
HAZARDS=['তাপপ্রবাহ','খরা','পানির সংকট','অতিবৃষ্টি','বন্যা','আকস্মিক বন্যা','জলাবদ্ধতা','ঘূর্ণিঝড়','জলোচ্ছ্বাস','কালবৈশাখী / ঝড়','বজ্রপাত','শিলাবৃষ্টি','নদীভাঙন','ভূমিধস','লবণাক্ততা বৃদ্ধি','শৈত্যপ্রবাহ','ঘন কুয়াশা','অন্যান্য']
HEALTH=['মাসিকে ব্যথা / তীব্র খিঁচুনি','অতিরিক্ত মাসিক রক্তপাত','দীর্ঘদিন মাসিক রক্তপাত','অনিয়মিত মাসিক','মাসিক বন্ধ / দেরি','মাসিকের মাঝখানে রক্তপাত','সহবাসের পরে রক্তপাত','মাসিকের আগে শারীরিক / মানসিক অস্বস্তি','তলপেট / শ্রোণিতে ব্যথা','অস্বাভাবিক স্রাব / দুর্গন্ধ','যোনি / বাহ্যিক যৌনাঙ্গে চুলকানি','যৌনাঙ্গে জ্বালাপোড়া / ফোলা','যৌনাঙ্গে ঘা / ফুসকুড়ি','যোনিতে শুষ্কতা','সহবাসে ব্যথা','যৌন আগ্রহ / সক্ষমতা নিয়ে উদ্বেগ','প্রস্রাবে ব্যথা / জ্বালাপোড়া','ঘন ঘন প্রস্রাব / তাগিদ','প্রস্রাব ধরে রাখতে সমস্যা','যোনিপথে ভারী ভাব / কিছু নেমে আসার অনুভূতি','গর্ভধারণ নিয়ে উদ্বেগ','গর্ভাবস্থায় রক্তপাত','গর্ভাবস্থায় তলপেটে ব্যথা','প্রসব-পরবর্তী রক্তপাত / অস্বস্তি','প্রসব-পরবর্তী জ্বর / দুর্গন্ধযুক্ত স্রাব','বুকের দুধ খাওয়াতে ব্যথা / স্তনে সমস্যা','সন্তান ধারণে অসুবিধা','গর্ভপাত / গর্ভহানি নিয়ে উদ্বেগ','জন্মনিয়ন্ত্রণের পার্শ্বপ্রতিক্রিয়া','যৌনবাহিত সংক্রমণ নিয়ে উদ্বেগ','মেনোপজের উপসর্গ','মেনোপজের পরে রক্তপাত','চিকিৎসক-নির্ণীত প্রজনন রোগের সমস্যা','মাসিক পরিচর্যার পানি / উপকরণের অভাব','অন্যান্য']
EXCLUSIVE=['কোনোটিই নয়','জানি না / মনে নেই','প্রযোজ্য নয়','বলতে চাই না']
def validate(s):
 if not isinstance(s,dict) or s.get('version') not in [1,2]:raise ValueError('Invalid survey version')
 kind=s.get('kind')
 if kind not in ['climate','disaster','reproductive']:raise ValueError('Invalid survey type')
 basis=s.get('basis','typical');year=s.get('year','')
 if basis not in ['typical','year'] or not isinstance(year,str) or (basis=='year' and (len(year)!=4 or not year.isdecimal())):raise ValueError('বাংলা সাল লিখুন / Enter Bengali year')
 rows=s.get('rows')
 if not isinstance(rows,list) or len(rows)!=(9 if kind=='climate' else 12):raise ValueError('সবগুলো সারির উত্তর দিন / Complete every row')
 clean=[]
 for i,r in enumerate(rows):
  if not isinstance(r,dict):raise ValueError('Invalid row')
  if kind=='climate':
   if r.get('key')!=['heat','rain','cold'][i//3]+'_'+str(i%3):raise ValueError('Invalid season or intensity')
   month=r.get('month');days=r.get('days');state=r.get('state','observed')
   if state not in ['observed','none','unknown']:raise ValueError('Invalid observation')
   if state=='observed' and (not isinstance(month,str) or not month.strip() or len(month)>200 or not isinstance(days,str) or not days.strip() or len(days)>100):raise ValueError('প্রতি মাত্রায় মাস ও দিন লিখুন / Enter month and days for every intensity')
   clean.append({'key':r['key'],'state':state,'month':month.strip() if state=='observed' else '', 'days':days.strip() if state=='observed' else ''})
  else:
   if r.get('month')!=MONTHS[i]:raise ValueError('Invalid month order')
   choices=r.get('choices');allowed=(HAZARDS if kind=='disaster' else HEALTH)+EXCLUSIVE
   if not isinstance(choices,list) or not choices or any(not isinstance(x,str) or x not in allowed for x in choices) or len(choices)!=len(set(choices)):raise ValueError('প্রতি মাসে উত্তর দিন / Select an answer for each month')
   if any(x in EXCLUSIVE for x in choices) and len(choices)!=1:raise ValueError('None/unknown cannot be combined with a problem')
   other=r.get('other','')
   if not isinstance(other,str) or len(other)>500 or (any(x in choices for x in ['অন্যান্য','চিকিৎসক-নির্ণীত প্রজনন রোগের সমস্যা']) and not other.strip()):raise ValueError('অন্যান্য সমস্যাটি লিখুন / Describe other')
   clean.append({'month':MONTHS[i],'choices':choices,'other':other.strip() if any(x in choices for x in ['অন্যান্য','চিকিৎসক-নির্ণীত প্রজনন রোগের সমস্যা']) else ''})
 if s['version']==2:return {'version':2,'kind':kind,'rows':clean}
 return {'version':1,'kind':kind,'basis':basis,'year':year if basis=='year' else '', 'rows':clean}
