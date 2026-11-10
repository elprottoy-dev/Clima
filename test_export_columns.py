import unittest,zipfile,io
import clinical
class ExportColumns(unittest.TestCase):
 def test_mixed_reports(self):
  row=clinical.seasonal_columns({'kind':'climate','rows':[{'key':'heat_0','state':'observed','month':'বৈশাখ','days':'১০ দিন'}]})
  data=clinical.xlsx({'Cases':[{'id':1},{'id':2,**row}]})
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   xml=z.read('xl/worksheets/sheet1.xml').decode()
   self.assertIn('বৈশাখ',xml);self.assertIn('১০ দিন',xml);self.assertIn('হালকা',xml)
 def test_monthly_answers(self):
  row=clinical.seasonal_columns({'kind':'disaster','rows':[{'month':'আষাঢ়','choices':['বন্যা','অতিবৃষ্টি'],'other':''}]})
  self.assertEqual(row['আষাঢ় — নির্বাচিত সমস্যা'],'বন্যা; অতিবৃষ্টি')
