// Disposable PostgreSQL-compatible integration environment. Synthetic data only.
import {PGlite} from '@electric-sql/pglite';
import {pgcrypto} from '@electric-sql/pglite/contrib/pgcrypto';
import {PGLiteSocketServer} from '@electric-sql/pglite-socket';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const db=await PGlite.create({extensions:{pgcrypto}});
await db.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE SCHEMA extensions;');
const server=new PGLiteSocketServer({db,host:'127.0.0.1',port:55432});
await server.start();
const child=spawn(process.env.PYTHON||'python',['test_postgres_integration.py'],{cwd:fileURLToPath(new URL('../',import.meta.url)),env:{...process.env,CLIMA_TEST_POSTGRES:'postgresql://postgres@127.0.0.1:55432/postgres'},stdio:'inherit'});
child.on('error',async()=>{await server.stop();await db.close();process.exit(1)});
child.on('exit',async code=>{await server.stop();await db.close();process.exit(code??1)});
