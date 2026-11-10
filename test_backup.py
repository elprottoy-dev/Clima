import unittest,tempfile,sqlite3
from pathlib import Path
from cryptography.fernet import Fernet,InvalidToken
import backup
class Backups(unittest.TestCase):
 def test_roundtrip_and_protection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);db=root/'source.db';key=Fernet.generate_key();secret=Fernet(key).encrypt(b'private clinical entry')
   with sqlite3.connect(db) as c:c.execute('CREATE TABLE records(value BLOB)');c.execute('INSERT INTO records VALUES(?)',(secret,))
   path=root/'backup.clima';password='Unique-backup-passphrase-123'
   backup.create(db,key.decode(),path,password)
   with self.assertRaises(FileExistsError):backup.create(db,key.decode(),path,password)
   with self.assertRaises(InvalidToken):backup.verify(path,'Incorrect-passphrase-123')
   restored=backup.restore(path,password,root/'restored')
   with sqlite3.connect(restored/'clima.sqlite3') as c:value=c.execute('SELECT value FROM records').fetchone()[0]
   self.assertEqual(Fernet((restored/'private/data.key').read_bytes()).decrypt(value),b'private clinical entry')
   with self.assertRaises(FileExistsError):backup.restore(path,password,restored)
   raw=bytearray(path.read_bytes());raw[-10]^=1;path.write_bytes(raw)
   with self.assertRaises(InvalidToken):backup.verify(path,password)
if __name__=='__main__':unittest.main()
