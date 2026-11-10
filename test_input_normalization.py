import unittest
from input_normalization import normalize_answers
class DigitsTest(unittest.TestCase):
 def test_nested_answers_and_leading_zero(self):
  self.assertEqual(normalize_answers({'phone':'০১৭১২৩৪৫৬৭৮','answers':[{'days':'১২','ward':'ওয়ার্ড ৩'}],'name':'ফাতেমা'}),{'phone':'01712345678','answers':[{'days':'12','ward':'ওয়ার্ড 3'}],'name':'ফাতেমা'})
 def test_credentials_and_case_unchanged(self):
  d={'password':'AbC০১২','new_password':'X১','token':'Ab১','subscription':{'endpoint':'১'},'occupation':'Nurse A১'}
  out=normalize_answers(d)
  for k in ['password','new_password','token','subscription']:self.assertEqual(out[k],d[k])
  self.assertEqual(out['occupation'],'Nurse A1')
