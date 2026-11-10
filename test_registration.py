import unittest,datetime
import registration
from test_upgrade import UpgradeFlow
class RegistrationFlow(UpgradeFlow):
 def data(self):
  v=registration.LOCATIONS[0];d=v['districts'][0];u=d['upazilas'][0]
  return dict(name_bn='ফাতেমা',phone='01712345678',birth_date='1998-05-12',marital_status='unmarried',occupation='শিক্ষার্থী',division=v['bn_name'],district=d['name'],upazila=u['bn_name'],area_type='union',local_area=u['unions'][0]['bn_name'],village='নমুনা গ্রাম',profile_consent=True,password='Strong-pass-12345')
 def test_profile_flow(self):
  d=self.data();status,r=self.call('register',d);self.assertEqual(status,200,r)
  user=self.call('me',token=r['token'])[1]['user'];self.assertEqual(user['name_bn'],'ফাতেমা')
  status,export=self.call('admin/user-record?uid='+str(user['id']),token=self.admin);self.assertEqual(status,200,export);self.assertEqual(export['Users'][0]['ফোন নম্বর'],d['phone']);self.assertEqual(export['Users'][0]['বৈবাহিক অবস্থা'],'অবিবাহিত')
  self.assertEqual(self.call('login',dict(username=d['phone'],password=d['password']))[0],200)
  self.assertEqual(self.call('register',d)[0],409)
 def test_marriage_validation(self):
  d=self.data();d.update(marital_status='married',marriage_age='20',children='1',pregnant='no',husband_earns='no',husband_no_income_reason='পড়াশোনা করেন',husband_occupation='শিক্ষার্থী',income_source='পরিবারের সহায়তা',marriage_date='2018-06-01')
  p,age,phone=registration.validate(d);self.assertEqual(p['children'],1)
  d['marriage_date']='2010-06-01';self.assertRaises(ValueError,registration.validate,d)
  d['marital_status']='unmarried';p,_,_=registration.validate(d);self.assertNotIn('husband_occupation',p)
 def test_bad_location_and_birth(self):
  d=self.data();d['birth_date']='2099-01-01';self.assertRaises(ValueError,registration.validate,d)
  d=self.data();d['local_area']='অজানা';self.assertRaises(ValueError,registration.validate,d)
