"""Run existing HTTP behavioral tests against an isolated local PostgreSQL instance.
Never run this on a real patient database: an explicit test URL is required and
only loopback hosts are accepted; the clima schema is reset before every test.
"""
import os,unittest
from pathlib import Path
from urllib.parse import urlsplit

def main():
 url=os.getenv('CLIMA_TEST_POSTGRES','')
 if urlsplit(url).hostname not in ['127.0.0.1','localhost']:raise SystemExit('Set CLIMA_TEST_POSTGRES to a disposable localhost PostgreSQL database')
 os.environ['CLIMA_DATABASE_URL']=url;os.environ['CLIMA_PG_SSLMODE']='disable'
 import psycopg,test_server,test_clinical,test_upgrade,test_cloud,test_seasonal
 from cryptography.fernet import Fernet
 os.environ['CLIMA_DATA_KEY']=Fernet.generate_key().decode()
 def reset():
  with psycopg.connect(url,sslmode='disable') as c:
   c.execute('DROP SCHEMA IF EXISTS clima CASCADE')
   c.execute(Path('deployment/postgres-bootstrap.sql').read_text())
 for cls in [test_server.Flow,test_clinical.ClinicalFlow]:
  original=cls.setUpClass
  def setup_class(cls,original=original):reset();original()
  cls.setUpClass=classmethod(setup_class)
 original=test_upgrade.UpgradeFlow.setUp
 def setup(self):reset();original(self)
 test_upgrade.UpgradeFlow.setUp=setup
 test_cloud.Cloud.setUp=setup
 suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in [test_server.Flow,test_clinical.ClinicalFlow,test_upgrade.UpgradeFlow,test_cloud.Cloud])
 suite.addTests([test_seasonal.SeasonalFlow('test_surveys'),test_seasonal.SeasonalFlow('test_messages')])
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 raise SystemExit(not result.wasSuccessful())
if __name__=='__main__':main()
